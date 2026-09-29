# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: high_tail_latency
- Severity: warning
- Duration: 5m
- Kênh thông báo: Slack (#llmops-alerts)
- SLI/SLO liên quan: `primary_slo.fast_successful_requests` (latency <= 3000ms)
- Điều kiện và thời gian duy trì: Latency P95 > 3000ms duy trì liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Phản hồi chậm chạp, giao diện người dùng có thể bị treo hoặc timeout
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Latency kiểm tra P95/P99 và mốc thời gian bắt đầu tăng.
  2. Lọc file `data/logs.jsonl` tìm request có `latency_ms > 3000` và trích xuất `correlation_id`.
  3. Mở Langfuse trace tương ứng để xem waterfall: kiểm tra xem span `retrieval` hay `fake-llm-generate` chiếm phần lớn thời gian.
- Mitigation tạm thời: Bật cache, giảm độ sâu retrieval `doc_count`, hoặc chuyển lưu lượng sang node dự phòng.
- Owner: llmops-team

## Alert 2

- Tên: high_error_rate
- Severity: critical
- Duration: 3m
- Kênh thông báo: Slack (#llmops-critical)
- SLI/SLO liên quan: `guardrails.error_rate_pct_max` (ngưỡng tối đa 2%)
- Điều kiện và thời gian duy trì: Tỷ lệ lỗi `request_failed` / `request_received` > 2% duy trì trong 3 phút
- Ảnh hưởng tới người dùng: Người dùng nhận phản hồi lỗi HTTP 500, ngắt quãng trải nghiệm
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Errors trên Dashboard xem loại lỗi phổ biến (`error_type`).
  2. Lọc log `event == "request_failed"` trong `data/logs.jsonl` để xem chi tiết `payload.detail`.
  3. Mở Langfuse trace của các request lỗi để xác định span ném ra ngoại lệ.
- Mitigation tạm thời: Kích hoạt circuit breaker, rollback release gần nhất, hoặc cô lập module/endpoint bị lỗi.
- Owner: llmops-oncall

## Alert 3

- Tên: retrieval_degradation
- Severity: critical
- Duration: 5m
- Kênh thông báo: Slack (#rag-alerts)
- SLI/SLO liên quan: `guardrails.retrieval_success_rate_pct_min` (tối thiểu 90%)
- Điều kiện và thời gian duy trì: Tỷ lệ `tool_success == true` giảm xuống dưới 90% liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Câu trả lời thiếu chính xác, mô hình phải dùng fallback chung chung hoặc trả về lỗi
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Error rate and retrieval success trên Dashboard xem tỷ lệ retrieval thành công.
  2. Lọc `data/logs.jsonl` với `tool_name == "retrieval"` và `tool_success == false`.
  3. Kiểm tra tình trạng vector store hoặc dịch vụ search indexing.
- Mitigation tạm thời: Bật chế độ direct fallback answering (không gọi RAG), restart dịch vụ vector store hoặc phục hồi index từ backup.
- Owner: rag-search-team
