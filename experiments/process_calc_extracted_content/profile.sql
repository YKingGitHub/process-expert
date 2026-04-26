-- Read-only profiling queries for the deterministic calculation feasibility POC.
--
-- Usage:
--   sqlite3 -header -column /root/process-expert/output/unified_extract.db \
--     < experiments/process_calc_extracted_content/profile.sql

.print '== table counts =='
select 'lookup_records' as table_name, count(*) as count from lookup_records
union all select 'computation_methods', count(*) from computation_methods
union all select 'knowledge_records', count(*) from knowledge_records
union all select 'process_card_records', count(*) from process_card_records;

.print ''
.print '== process card route groups =='
select
  part_name,
  table_ref,
  min(page_num) as first_page,
  count(*) as steps,
  group_concat(distinct operation_name) as operations
from process_card_records
group by part_name, table_ref
order by first_page, table_ref;

.print ''
.print '== operation name frequency =='
select operation_name, count(*) as count
from process_card_records
group by operation_name
order by count desc, operation_name
limit 40;

.print ''
.print '== rows with explicit numeric or allowance signals =='
select
  page_num,
  part_name,
  table_ref,
  step_no,
  operation_name,
  operation_content
from process_card_records
where operation_content like '%余量%'
   or operation_content like '%±%'
   or operation_content like '%+%'
   or operation_content like '%φ%'
order by page_num, step_no
limit 80;

.print ''
.print '== computation methods with numeric examples =='
select
  id,
  page_num,
  method_name,
  substr(description, 1, 80) as description,
  substr(example_json, 1, 180) as example_json
from computation_methods
where example_json is not null
  and example_json != 'null'
order by id;
