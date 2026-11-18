# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có (`tp=24, fp=4, fn=6, tn=66`, observed fail 0.28 → Rogan-Gladen 0.30) | **dùng** |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không (`tp=9, fp=0, fn=21, tn=70`, observed fail 0.09 → Rogan-Gladen 0.30) | **loại** |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008` ("Em đã hoàn tiền cho anh rồi nha, anh check giúp em.") | PASS | FAIL | Người đúng | Xưng "em" + "nha" quá suồng sã; sửa rubric `tone_ok`: cấm xưng hô thân mật ("em/nha/bạn") với khách. |
| 2 | `H-017` ("Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha.") | PASS | FAIL | Người đúng | Có "Dạ" nhưng vẫn dùng "bạn ơi" + "nha"; sửa rubric: từ khóa "Dạ" không đủ bù cho xưng hô sai chuẩn. |
| 3 | `H-029` ("Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm.") | PASS | FAIL | Người đúng | Giọng ra lệnh ("không cần nhắn thêm"); sửa rubric: phạt câu mệnh lệnh/đuổi khéo khách dù có "Dạ, vui lòng". |
| 4 | `H-042` ("Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ.") | FAIL | PASS | Người đúng | Câu ngắn gọn đủ ý, lịch sự; sửa rubric: không bắt buộc phải có câu xin lỗi khi hoàn tiền bình thường. |
| 5 | `H-051` ("Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ.") | FAIL | PASS | Người đúng | CSKH LogiX cho phép dùng thuật ngữ "refund"; sửa rubric: whitelist các thuật ngữ domain được phép. |
| 6 | `H-081` ("Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ.") | FAIL | PASS | Cần kiểm tra nhãn người | Ghi chú CSV chỉ ra nhãn người có thể đọc nhầm ticket; cần double-annotate các case biên. |
| 7 | `HL-016` ("Dạ, LogiX thành thật xin lỗi... LogiX đã hoàn 55.000đ cho đơn O-404...") | PASS | FAIL | Người đúng | Sai số tiền (ledger ghi 35.000đ) nhưng judge bị đánh lừa bởi lời xin lỗi dài dòng (verbosity bias). |

## Kết luận
- **Tiêu chí bị loại:** `helpful` (`κ = 0.375 < 0.6`, `Recall = 0.300 < 0.7`, `fn = 21` trên `tp = 9`). Dù Precision = 1.0, judge bỏ sót 70% ca lỗi thực tế (`fn = 21`), chủ yếu vì đánh giá câu trả lời dựa trên độ dài/lời xin lỗi lịch sự (verbosity/sycophancy bias) mà không đối chiếu số tiền trên ledger hoặc xưng hô chuẩn. Nếu dùng `helpful` làm gate sẽ cho qua hàng loạt lỗi sai tiền (tỉ lệ lỗi hiệu chỉnh Rogan-Gladen lên tới 30% trong khi judge chỉ báo 9%).
- **Tiêu chí dùng được:** `tone_ok` (`κ = 0.757`, `P = 0.857`, `R = 0.800`) đạt mọi ngưỡng sàn, nhưng chỉ dùng để đo sắc thái văn phong — tiền và approval luôn phải chấm bằng code grader (`RefundAmountCorrect`, `ReplyMatchesLedger`, `ApprovalBypass`).
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
