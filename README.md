# SiliconFlow Voice Clone Mini App

## New feature
Reference audio text can now be auto-transcribed using SiliconFlow ASR before uploading.

## Local run
```bash
pip install -r requirements.txt
streamlit run siliconflow_voice_clone_app.py
```

## Streamlit Cloud secrets
Add these in the Streamlit Cloud Secrets panel:

```toml
SILICONFLOW_API_KEY = "your_api_key"
APP_PASSWORD = "optional_shared_password"
```
