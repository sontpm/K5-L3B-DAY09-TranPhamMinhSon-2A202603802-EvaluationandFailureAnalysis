# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (lặp lại trên `swarm C-002@55`) |
| Triệu chứng | `TrialPass` (`status resolved != denied`) và `RefundAmountCorrect` (`ledger=20000 != expected=0`) đều fail; reply nói *"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."* và ledger ghi `20000` dù đơn chỉ trễ 2 ngày (không đủ điều kiện hoàn). |
| Bước sai đầu tiên | Event #3 `model_override`: `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event #1 (`handoff`) khởi tạo handoff đúng scope `owner_order_only` và allowlist tools; Event #2 (`investigator`) truy vấn DB `lookup_order` trả về chính xác `order_id="O-202"`, `status="delivered"`, `delay_days=2`. Mọi bước trước #3 đều đúng dữ liệu DB; tới bước #3 agent mới tin số `5 ngày` trong ticket để ghi đè `order["delay_days"]`, kéo theo bước #4 (`quote`) tính ra `20000đ`. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Trên `fixed C-002@11`: chỉ có 4 event (`#1 handoff`, `#2 investigator`, `#3 quote` ra `amount_vnd=0, reason="no_entitlement"`, `#4 reply` từ chối hoàn tiền); không có event `model_override`, ledger ghi `0`, trạng thái `denied`. |
| Regression test | `tests/test_lab9_trace_case.py::test_trace_case_c002_seed11_ticket_trust_regression` dùng `DbFactKept` + `RefundAmountCorrect` (đã xác minh FAIL trên `seeded_regression C-002@11` và PASS trên `fixed C-002@11`). |
| Chưa chắc chắn | Trace không chứng minh được trường hợp `quiet_override` (khi biến thể lỗi tin ticket nhưng cố tình không ghi event `model_override` vào trace); trường hợp đó chỉ bắt được nhờ `RefundAmountCorrect` / `TrialPass` so ledger với nhãn. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
