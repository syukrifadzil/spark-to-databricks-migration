-- Wall-clock time of the latest pipeline updates, from the pipeline's event log.
-- total_seconds runs from the first event of the update (created) to the last (completed or
-- failed). It includes the wait for serverless resources, which running_seconds leaves out.
-- Run in the SQL editor; record the rows for the update ids named in benchmarks/README.md.
SELECT origin.update_id,
       min(timestamp) AS first_event,
       max(timestamp) AS last_event,
       round((unix_millis(max(timestamp)) - unix_millis(min(timestamp))) / 1000, 1) AS total_seconds,
       round((unix_millis(max(timestamp))
              - unix_millis(min(timestamp) FILTER (WHERE details:update_progress.state::string = 'RUNNING'))) / 1000, 1)
         AS running_seconds,
       max_by(details:update_progress.state::string, timestamp) FILTER (WHERE event_type = 'update_progress')
         AS final_state
FROM event_log('65b949fd-556c-47bd-ac1f-08855e9f7bd4')
WHERE origin.update_id IS NOT NULL
GROUP BY origin.update_id
ORDER BY first_event DESC
LIMIT 10;
