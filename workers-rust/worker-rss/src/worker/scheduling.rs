use std::collections::{BTreeMap, HashSet, VecDeque};

use crate::feed::scheduling_host_key;
use crate::model::{ClaimedRssTask, RssResult};

use super::RssGatewayState;

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub(crate) struct TaskKey {
    pub(crate) task_id: u64,
    pub(crate) execution_id: u64,
}

pub(crate) struct TaskProgress {
    total_feeds: usize,
    remaining_feeds: usize,
    results: Vec<Option<RssResult>>,
}

impl TaskProgress {
    pub(crate) fn new(task: &ClaimedRssTask) -> Self {
        Self {
            total_feeds: task.feeds.len(),
            remaining_feeds: task.feeds.len(),
            results: vec![None; task.feeds.len()],
        }
    }

    pub(crate) fn push_result(&mut self, feed_index: usize, result: RssResult) {
        self.results[feed_index] = Some(result);
        self.remaining_feeds = self.remaining_feeds.saturating_sub(1);
    }

    pub(crate) fn is_complete(&self) -> bool {
        self.remaining_feeds == 0
    }

    pub(crate) fn into_results(self) -> super::Result<Vec<RssResult>> {
        self.results
            .into_iter()
            .enumerate()
            .map(|(feed_index, result)| {
                result.ok_or_else(|| {
                    std::io::Error::other(format!("missing RSS result for feed index {feed_index}"))
                        .into()
                })
            })
            .collect()
    }
}

#[derive(Clone)]
pub(crate) struct ScheduledFeed {
    pub(crate) task_key: TaskKey,
    pub(crate) feed_index: usize,
    pub(crate) job_id: String,
    pub(crate) ingest: bool,
    pub(crate) feed: crate::model::RssFeedPayload,
}

pub(crate) struct CompletedFeed {
    pub(crate) host_key: String,
    pub(crate) scheduled_feed: ScheduledFeed,
    pub(crate) result: RssResult,
}

pub(crate) fn enqueue_task(
    active_tasks: &mut BTreeMap<TaskKey, TaskProgress>,
    pending_by_host: &mut BTreeMap<String, VecDeque<ScheduledFeed>>,
    task: ClaimedRssTask,
) {
    let task_key = TaskKey {
        task_id: task.task_id,
        execution_id: task.execution_id,
    };

    for (feed_index, feed) in task.feeds.iter().cloned().enumerate() {
        pending_by_host
            .entry(scheduling_host_key(&feed))
            .or_default()
            .push_back(ScheduledFeed {
                task_key,
                feed_index,
                job_id: task.job_id.clone(),
                ingest: task.ingest,
                feed,
            });
    }

    active_tasks.insert(task_key, TaskProgress::new(&task));
}

pub(crate) fn processing_state(
    active_tasks: &BTreeMap<TaskKey, TaskProgress>,
    pending_by_host: &BTreeMap<String, VecDeque<ScheduledFeed>>,
) -> RssGatewayState {
    let feeds_claimed: usize = active_tasks.values().map(|task| task.total_feeds).sum();
    let queued_feeds: usize = pending_by_host.values().map(VecDeque::len).sum();
    let first_task = active_tasks.iter().next().map(|(task_key, _)| *task_key);

    RssGatewayState {
        active: true,
        connection_state: "processing".to_string(),
        pending_tasks: active_tasks.len() as u32,
        current_task_id: first_task.map(|task_key| task_key.task_id),
        current_execution_id: first_task.map(|task_key| task_key.execution_id),
        current_task_label: Some(format!(
            "{} rss tasks claimed ({} feeds, {} queued)",
            active_tasks.len(),
            feeds_claimed,
            queued_feeds
        )),
        desired_state: Some("running".to_string()),
        ..Default::default()
    }
}

pub(crate) fn claiming_state() -> RssGatewayState {
    RssGatewayState {
        active: true,
        connection_state: "claiming".to_string(),
        pending_tasks: 0,
        desired_state: Some("running".to_string()),
        ..Default::default()
    }
}

pub(crate) fn idle_state() -> RssGatewayState {
    RssGatewayState {
        active: true,
        connection_state: "idle".to_string(),
        pending_tasks: 0,
        desired_state: Some("running".to_string()),
        ..Default::default()
    }
}

pub(crate) fn next_available_host(
    pending_by_host: &BTreeMap<String, VecDeque<ScheduledFeed>>,
    active_hosts: &HashSet<String>,
) -> Option<String> {
    pending_by_host
        .keys()
        .find(|host_key| !active_hosts.contains(*host_key))
        .cloned()
}

pub(crate) fn pop_next_feed(
    pending_by_host: &mut BTreeMap<String, VecDeque<ScheduledFeed>>,
    host_key: &str,
) -> Option<ScheduledFeed> {
    let mut queue = pending_by_host.remove(host_key)?;
    let next_feed = queue.pop_front();
    if !queue.is_empty() {
        pending_by_host.insert(host_key.to_string(), queue);
    }
    next_feed
}
