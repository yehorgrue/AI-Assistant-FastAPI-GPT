copilot storage init \
--name azara-ai-db \
--storage-type Aurora \
--workload azara-api \
--lifecycle environment \
--engine PostgreSQL \
--initial-db azara-api-db \
--serverless-version v2