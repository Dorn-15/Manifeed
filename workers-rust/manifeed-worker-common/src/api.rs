use reqwest::header::{AUTHORIZATION, CONTENT_TYPE};
use serde::de::DeserializeOwned;
use serde::Serialize;

use crate::error::{Result, WorkerError};

#[derive(Clone, Debug)]
pub struct ApiClient {
    base_url: String,
    client: reqwest::Client,
}

impl ApiClient {
    pub fn new(base_url: impl Into<String>) -> Result<Self> {
        let base_url = base_url.into().trim_end_matches('/').to_string();
        if base_url.is_empty() {
            return Err(WorkerError::Config("MANIFEED_API_URL is empty".to_string()));
        }
        let client = reqwest::Client::builder()
            .user_agent("manifeed-worker-rust/0.1.0")
            .build()?;
        Ok(Self { base_url, client })
    }

    pub async fn get_json<T>(&self, path: &str, bearer_token: Option<&str>) -> Result<T>
    where
        T: DeserializeOwned,
    {
        let request = self.authorized_request(self.client.get(self.url(path)?), bearer_token);
        self.handle_response(request.send().await?).await
    }

    pub async fn post_json<TReq, TRes>(
        &self,
        path: &str,
        payload: &TReq,
        bearer_token: Option<&str>,
    ) -> Result<TRes>
    where
        TReq: Serialize + ?Sized,
        TRes: DeserializeOwned,
    {
        let request = self.authorized_request(self.client.post(self.url(path)?), bearer_token);
        self.handle_response(
            request
                .header(CONTENT_TYPE, "application/json")
                .json(payload)
                .send()
                .await?,
        )
        .await
    }

    fn url(&self, path: &str) -> Result<String> {
        let normalized_path = if path.starts_with('/') {
            path.to_string()
        } else {
            format!("/{path}")
        };
        Ok(format!("{}{}", self.base_url, normalized_path))
    }

    fn authorized_request(
        &self,
        request: reqwest::RequestBuilder,
        bearer_token: Option<&str>,
    ) -> reqwest::RequestBuilder {
        if let Some(token) = bearer_token {
            request.header(AUTHORIZATION, format!("Bearer {token}"))
        } else {
            request
        }
    }

    async fn handle_response<T>(&self, response: reqwest::Response) -> Result<T>
    where
        T: DeserializeOwned,
    {
        let status = response.status();
        let bytes = response.bytes().await?;
        if !status.is_success() {
            let message = serde_json::from_slice::<serde_json::Value>(&bytes)
                .ok()
                .and_then(|value| {
                    value
                        .get("detail")
                        .and_then(|detail| detail.as_str())
                        .map(str::to_string)
                })
                .unwrap_or_else(|| String::from_utf8_lossy(&bytes).to_string());
            return Err(WorkerError::Api {
                status: status.as_u16(),
                message,
            });
        }
        Ok(serde_json::from_slice::<T>(&bytes)?)
    }
}
