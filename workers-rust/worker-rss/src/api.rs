use std::sync::Arc;

use async_trait::async_trait;
use manifeed_worker_common::{
    ApiClient, WorkerAuthenticator, WorkerTaskClaim, WorkerTaskClaimRequest,
};
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;

use crate::config::RssWorkerConfig;
use crate::model::{ClaimedRssTask, RssFeedPayload, RssResult};
use crate::worker::{Result, RssGateway, RssGatewayState};

#[derive(Deserialize)]
struct RssTaskPayload {
    job_id: String,
    ingest: bool,
    feeds: Vec<RssFeedPayload>,
}

#[derive(Serialize)]
struct RssTaskCompleteRequest {
    task_id: u64,
    execution_id: u64,
    result_events: Vec<RssResultEvent>,
}

#[derive(Serialize)]
struct RssResultEvent {
    payload: RssResult,
}

#[derive(Serialize)]
struct RssTaskFailRequest {
    task_id: u64,
    execution_id: u64,
    error_message: String,
}

#[derive(Clone)]
pub struct HttpRssGateway {
    api_client: ApiClient,
    authenticator: Arc<Mutex<WorkerAuthenticator>>,
    lease_seconds: u32,
}

impl HttpRssGateway {
    pub fn new(config: &RssWorkerConfig) -> Result<Self> {
        Ok(Self {
            api_client: ApiClient::new(config.api_url.clone())?,
            authenticator: Arc::new(Mutex::new(WorkerAuthenticator::new(config.auth.clone())?)),
            lease_seconds: config.lease_seconds,
        })
    }

    async fn bearer_token(&self) -> Result<String> {
        let mut authenticator = self.authenticator.lock().await;
        Ok(authenticator.ensure_session(&self.api_client).await?)
    }

    fn parse_claim(task: WorkerTaskClaim) -> Result<ClaimedRssTask> {
        let payload = serde_json::from_value::<RssTaskPayload>(task.payload)?;
        Ok(ClaimedRssTask {
            task_id: task.task_id,
            execution_id: task.execution_id,
            job_id: payload.job_id,
            ingest: payload.ingest,
            feeds: payload.feeds,
        })
    }
}

#[async_trait]
impl RssGateway for HttpRssGateway {
    async fn claim(&self, count: usize) -> Result<Vec<ClaimedRssTask>> {
        let token = self.bearer_token().await?;
        let tasks = self
            .api_client
            .post_json::<_, Vec<WorkerTaskClaim>>(
                "/internal/workers/rss/claim",
                &WorkerTaskClaimRequest {
                    count: count.min(u32::MAX as usize) as u32,
                    lease_seconds: self.lease_seconds,
                },
                Some(&token),
            )
            .await?;
        tasks.into_iter().map(Self::parse_claim).collect()
    }

    async fn complete(
        &self,
        task_id: u64,
        execution_id: u64,
        results: Vec<RssResult>,
    ) -> Result<()> {
        let token = self.bearer_token().await?;
        self.api_client
            .post_json::<_, serde_json::Value>(
                "/internal/workers/rss/complete",
                &RssTaskCompleteRequest {
                    task_id,
                    execution_id,
                    result_events: results
                        .into_iter()
                        .map(|payload| RssResultEvent { payload })
                        .collect(),
                },
                Some(&token),
            )
            .await?;
        Ok(())
    }

    async fn fail(&self, task_id: u64, execution_id: u64, error_message: String) -> Result<()> {
        let token = self.bearer_token().await?;
        self.api_client
            .post_json::<_, serde_json::Value>(
                "/internal/workers/rss/fail",
                &RssTaskFailRequest {
                    task_id,
                    execution_id,
                    error_message,
                },
                Some(&token),
            )
            .await?;
        Ok(())
    }

    async fn update_state(&self, state: RssGatewayState) -> Result<()> {
        let token = self.bearer_token().await?;
        let state = state.sanitized();
        self.api_client
            .post_json::<_, serde_json::Value>("/internal/workers/rss/state", &state, Some(&token))
            .await?;
        Ok(())
    }
}
