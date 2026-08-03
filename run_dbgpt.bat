@echo off
setlocal
set DBGPT_HOME=e:\embed_agent\DB-GPT-main\pilot
set DBGPTS_HOME=e:\embed_agent\DB-GPT-main\pilot\.dbgpts
set DBGPTS_REPO_HOME=e:\embed_agent\DB-GPT-main\pilot\.dbgpts\repos
set PYTHONPATH=e:\embed_agent\DB-GPT-main\packages\dbgpt-app\src;e:\embed_agent\DB-GPT-main\packages\dbgpt-core\src;e:\embed_agent\DB-GPT-main\packages\dbgpt-ext\src;e:\embed_agent\DB-GPT-main\packages\dbgpt-serve\src;e:\embed_agent\DB-GPT-main\packages\dbgpt-storage\base\src
cd /d e:\embed_agent\DB-GPT-main
"e:\embed_agent\DB-GPT-main\.venv\Scripts\python.exe" -m dbgpt_app.dbgpt_server -c "%USERPROFILE%\.dbgpt\configs\openai.toml"
