-- 生产库 furui_aios 业务数据 seed（TASK-015 运行时页验收：任务/数据资产真实内容）
BEGIN;

INSERT INTO sales_tasks (company_id, customer_name, title, detail, priority, owner, due_date, status, source, created_by) VALUES
(16, '秦山核电', '汽轮机厂房日常巡检', '对汽轮机厂房 1-3 号机组进行例行巡检，检查轴承温度与振动值。', 'medium', '王欢', '2026-09-25', 'done', 'agent', 'admin'),
(16, '秦山核电', '反应堆冷却剂泵例行点检', '冷却剂泵 P-101 运行参数复核，关注轴封泄漏量是否超限。', 'high', '王欢', '2026-09-26', 'in_progress', 'agent', 'admin'),
(16, '秦山核电', '辐射监测站 MS-01 校准', '对辐射监测站 MS-01 进行季度校准，比对剂量率仪表读数。', 'high', '王欢', '2026-09-28', 'pending', 'agent', 'admin'),
(16, '秦山核电', '二回路水质取样分析', '二回路给水/蒸汽取样，检测电导率、pH 与溶解氧指标。', 'medium', '王欢', '2026-09-29', 'pending', 'agent', 'admin'),
(16, '秦山核电', '应急柴油发电机带载试验', '应急柴油发电机月度带载试验，验证黑启动能力。', 'high', '王欢', '2026-10-02', 'pending', 'agent', 'admin');

INSERT INTO data_datasets (company_id, source_id, name, kind, entity, row_count, version, schema_json, lineage_json, health_status, status) VALUES
(16, 'iot', '监测站实时数据', 'table', 'MonitoringStation', 5, 'v1', '[]', '{}', 'healthy', 'active'),
(16, 'erp', '巡检记录台账', 'table', 'InspectionRecord', 3, 'v1', '[]', '{}', 'healthy', 'active'),
(16, 'erp', '设备台账', 'table', 'Device', 8, 'v1', '[]', '{}', 'healthy', 'active');

COMMIT;