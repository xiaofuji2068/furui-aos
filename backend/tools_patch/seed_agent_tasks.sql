-- 生产库 furui_aios agent_tasks seed（TASK-015 运行时"最近任务"真实内容）
BEGIN;

INSERT INTO agent_tasks (company_id, agent_id, user_id, conversation_id, title, input_text, mode, status, priority, progress, result, error, retry_count, started_at, finished_at, brief) VALUES
(16, 3, 1, 'seed-insp-001', '汽轮机厂房日常巡检分析', '对汽轮机厂房 1-3 号机组巡检数据进行分析，输出异常项。', 'auto', 'completed', 2, 100, '巡检完成：轴承温度、振动值均在正常范围，无异常项。', '', 0, '2026-09-25 09:00:00', '2026-09-25 09:03:00', '{}'),
(16, 3, 1, 'seed-insp-002', '反应堆冷却剂泵点检复核', '复核冷却剂泵 P-101 轴封泄漏量与振动参数。', 'auto', 'in_progress', 3, 60, '', '', 0, '2026-09-26 10:00:00', NULL, '{}'),
(16, 1, 1, 'seed-sales-001', '核电客户合同履约分析', '汇总秦山核电合同执行状态与回款进度。', 'auto', 'pending', 3, 0, '', '', 0, NULL, NULL, '{}'),
(16, 2, 1, 'seed-kb-001', '辐射监测规程知识检索', '检索辐射监测站校准规程并摘要。', 'auto', 'pending', 2, 0, '', '', 0, NULL, NULL, '{}'),
(16, 4, 1, 'seed-ops-001', '应急柴油发电机带载试验评估', '评估月度带载试验结果与备件状态。', 'auto', 'pending', 2, 0, '', '', 0, NULL, NULL, '{}');

COMMIT;