use std::collections::{BTreeMap, HashSet, VecDeque};
use std::sync::Arc;

use tokio::task::JoinSet;
use tracing::warn;

use super::scheduling::{
    claiming_state, enqueue_task, idle_state, next_available_host, pop_next_feed, processing_state,
    CompletedFeed, ScheduledFeed, TaskKey, TaskProgress,
};
use super::{FeedFetcher, Result, RssGateway};
use crate::logging::stdout_log;
use crate::model::RssResult;

struct CompletedTaskAck {
    task_id: u64,
}

pub struct RssWorker<G, F> {
    pub(crate) gateway: G,
    fetcher: Arc<F>,
    max_in_flight_requests: usize,
    max_claimed_tasks: usize,
}

impl<G, F> RssWorker<G, F>
where
    G: RssGateway + Clone + Send + Sync + 'static,
    F: FeedFetcher + Send + Sync + 'static,
{
    pub fn new(
        gateway: G,
        fetcher: F,
        max_in_flight_requests: usize,
        max_claimed_tasks: usize,
    ) -> Self {
        Self {
            gateway,
            fetcher: Arc::new(fetcher),
            max_in_flight_requests: max_in_flight_requests.max(1),
            max_claimed_tasks: max_claimed_tasks.max(1),
        }
    }

    pub async fn run_once(&mut self) -> Result<bool> {
        let mut active_tasks = BTreeMap::<TaskKey, TaskProgress>::new();
        let mut pending_by_host = BTreeMap::<String, VecDeque<ScheduledFeed>>::new();
        let mut active_hosts = HashSet::new();
        let mut fetch_join_set = JoinSet::new();
        let mut completion_join_set = JoinSet::<Result<CompletedTaskAck>>::new();
        let mut state_join_set = JoinSet::<Result<()>>::new();
        let mut pending_state = None::<super::RssGatewayState>;
        let mut pending_completion_count = 0usize;
        let mut should_claim = true;
        let mut claimed_any_tasks = false;

        self.gateway.update_state(claiming_state()).await?;

        loop {
            reconcile_state_updates(&mut state_join_set, &mut pending_state, &self.gateway);

            while let Some(joined) = completion_join_set.try_join_next() {
                pending_completion_count = pending_completion_count.saturating_sub(1);
                let acknowledged_task = joined??;
                stdout_log(format!("return {}", acknowledged_task.task_id));
                should_claim = true;
            }

            if should_claim {
                let available_task_slots =
                    self.max_claimed_tasks.saturating_sub(active_tasks.len());
                if available_task_slots > 0 {
                    let claimed_tasks = self.gateway.claim(available_task_slots).await?;
                    if !claimed_tasks.is_empty() {
                        claimed_any_tasks = true;
                        for task in claimed_tasks {
                            stdout_log(format!("claim task {} received", task.task_id));
                            enqueue_task(&mut active_tasks, &mut pending_by_host, task);
                        }
                        queue_state_update(
                            &mut state_join_set,
                            &mut pending_state,
                            &self.gateway,
                            processing_state(&active_tasks, &pending_by_host),
                        );
                    }
                }
                should_claim = false;
            }

            while fetch_join_set.len() < self.max_in_flight_requests {
                let Some(host_key) = next_available_host(&pending_by_host, &active_hosts) else {
                    break;
                };
                let Some(scheduled_feed) = pop_next_feed(&mut pending_by_host, &host_key) else {
                    continue;
                };

                active_hosts.insert(host_key.clone());
                let fetcher = Arc::clone(&self.fetcher);
                fetch_join_set.spawn(async move {
                    let result = match fetcher
                        .fetch(
                            &scheduled_feed.job_id,
                            scheduled_feed.ingest,
                            &scheduled_feed.feed,
                        )
                        .await
                    {
                        Ok(result) => result,
                        Err(error) => RssResult::error(
                            scheduled_feed.job_id.as_str(),
                            scheduled_feed.ingest,
                            &scheduled_feed.feed,
                            error.to_string(),
                        ),
                    };
                    CompletedFeed {
                        host_key,
                        scheduled_feed,
                        result,
                    }
                });
            }

            if fetch_join_set.is_empty() {
                if active_tasks.is_empty() {
                    if pending_completion_count == 0 {
                        flush_state_updates(&mut state_join_set, &mut pending_state, &self.gateway)
                            .await;
                        self.gateway.update_state(idle_state()).await?;
                        return Ok(claimed_any_tasks);
                    }

                    let Some(joined) = completion_join_set.join_next().await else {
                        return Err(std::io::Error::other(
                            "worker is waiting for task completion acknowledgements but none are running",
                        )
                        .into());
                    };
                    pending_completion_count = pending_completion_count.saturating_sub(1);
                    let acknowledged_task = joined??;
                    stdout_log(format!("return {}", acknowledged_task.task_id));
                    should_claim = true;
                    continue;
                }

                return Err(std::io::Error::other(
                    "worker has claimed tasks but no active feed execution",
                )
                .into());
            }

            let completed_feed = tokio::select! {
                Some(joined) = fetch_join_set.join_next() => joined?,
                Some(joined) = completion_join_set.join_next(), if !completion_join_set.is_empty() => {
                    pending_completion_count = pending_completion_count.saturating_sub(1);
                    let acknowledged_task = joined??;
                    stdout_log(format!("return {}", acknowledged_task.task_id));
                    should_claim = true;
                    continue;
                }
            };
            active_hosts.remove(&completed_feed.host_key);

            let completed_task_key = {
                let task_progress = active_tasks
                    .get_mut(&completed_feed.scheduled_feed.task_key)
                    .ok_or_else(|| {
                        std::io::Error::other("missing task progress for completed feed")
                    })?;
                task_progress.push_result(
                    completed_feed.scheduled_feed.feed_index,
                    completed_feed.result,
                );
                if task_progress.is_complete() {
                    Some(completed_feed.scheduled_feed.task_key)
                } else {
                    None
                }
            };

            if let Some(task_key) = completed_task_key {
                let completed_task = active_tasks
                    .remove(&task_key)
                    .ok_or_else(|| std::io::Error::other("missing completed task state"))?;
                let results = completed_task.into_results()?;
                let gateway = self.gateway.clone();
                pending_completion_count += 1;
                completion_join_set.spawn(async move {
                    gateway
                        .complete(task_key.task_id, task_key.execution_id, results)
                        .await?;
                    Ok(CompletedTaskAck {
                        task_id: task_key.task_id,
                    })
                });
                should_claim = true;
                if !active_tasks.is_empty() || !pending_by_host.is_empty() {
                    queue_state_update(
                        &mut state_join_set,
                        &mut pending_state,
                        &self.gateway,
                        processing_state(&active_tasks, &pending_by_host),
                    );
                }
            }
        }
    }
}

fn queue_state_update<G>(
    state_join_set: &mut JoinSet<Result<()>>,
    pending_state: &mut Option<super::RssGatewayState>,
    gateway: &G,
    state: super::RssGatewayState,
) where
    G: RssGateway + Clone + Send + Sync + 'static,
{
    if state_join_set.is_empty() {
        let gateway = gateway.clone();
        state_join_set.spawn(async move { gateway.update_state(state).await });
        return;
    }

    *pending_state = Some(state);
}

fn reconcile_state_updates<G>(
    state_join_set: &mut JoinSet<Result<()>>,
    pending_state: &mut Option<super::RssGatewayState>,
    gateway: &G,
) where
    G: RssGateway + Clone + Send + Sync + 'static,
{
    while let Some(joined) = state_join_set.try_join_next() {
        match joined {
            Ok(Ok(())) => {}
            Ok(Err(error)) => warn!("rss worker state update failed: {error}"),
            Err(error) => warn!("rss worker state task join failed: {error}"),
        }

        if let Some(state) = pending_state.take() {
            let gateway = gateway.clone();
            state_join_set.spawn(async move { gateway.update_state(state).await });
        }
    }
}

async fn flush_state_updates<G>(
    state_join_set: &mut JoinSet<Result<()>>,
    pending_state: &mut Option<super::RssGatewayState>,
    gateway: &G,
) where
    G: RssGateway + Clone + Send + Sync + 'static,
{
    if let Some(state) = pending_state.take() {
        let gateway = gateway.clone();
        state_join_set.spawn(async move { gateway.update_state(state).await });
    }

    while let Some(joined) = state_join_set.join_next().await {
        match joined {
            Ok(Ok(())) => {}
            Ok(Err(error)) => warn!("rss worker state update failed: {error}"),
            Err(error) => warn!("rss worker state task join failed: {error}"),
        }
    }
}
