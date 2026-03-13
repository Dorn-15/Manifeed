use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RssWorkerStatus {
    Stopped,
    Starting,
    Authenticating,
    Idle,
    Claiming,
    Processing,
    Paused,
    BackendDisconnected,
    AuthRejected,
    Error,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct RssWorkerSnapshot {
    pub status: Option<RssWorkerStatus>,
    pub current_task_id: Option<u64>,
    pub current_execution_id: Option<u64>,
    pub current_task_label: Option<String>,
    pub current_feed_id: Option<u64>,
    pub current_feed_url: Option<String>,
    pub last_error: Option<String>,
}
