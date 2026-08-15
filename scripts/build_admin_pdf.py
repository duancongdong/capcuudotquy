from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "huong-dan-admin-cap-nhat-du-lieu.pdf"
FONT_DIR = Path(r"C:\Windows\Fonts")

pdfmetrics.registerFont(TTFont("Arial", str(FONT_DIR / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Bold", str(FONT_DIR / "arialbd.ttf")))

BLUE = colors.HexColor("#1769aa")
LIGHT_BLUE = colors.HexColor("#eaf4fb")
LIGHT_RED = colors.HexColor("#fff1f0")
TEXT = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#52606d")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="CoverTitle", fontName="Arial-Bold", fontSize=25, leading=31,
    textColor=BLUE, alignment=TA_CENTER, spaceAfter=9 * mm,
))
styles.add(ParagraphStyle(
    name="CoverSub", fontName="Arial", fontSize=12, leading=18,
    textColor=MUTED, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    name="H1VN", fontName="Arial-Bold", fontSize=17, leading=22,
    textColor=BLUE, spaceBefore=2 * mm, spaceAfter=5 * mm,
))
styles.add(ParagraphStyle(
    name="H2VN", fontName="Arial-Bold", fontSize=11.5, leading=15,
    textColor=TEXT, spaceBefore=3 * mm, spaceAfter=2 * mm,
))
styles.add(ParagraphStyle(
    name="BodyVN", fontName="Arial", fontSize=9.5, leading=14,
    textColor=TEXT, spaceAfter=2.5 * mm,
))
styles.add(ParagraphStyle(
    name="SmallVN", fontName="Arial", fontSize=8.3, leading=11.5,
    textColor=MUTED,
))
styles.add(ParagraphStyle(
    name="CodeVN", fontName="Arial-Bold", fontSize=9.2, leading=13,
    textColor=TEXT, backColor=colors.HexColor("#f4f6f8"),
    borderColor=colors.HexColor("#d9e2ec"), borderWidth=0.5,
    borderPadding=5, spaceAfter=2.5 * mm,
))
styles.add(ParagraphStyle(
    name="TableVN", fontName="Arial", fontSize=8.4, leading=11.5,
    textColor=TEXT,
))
styles.add(ParagraphStyle(
    name="TableHeadVN", fontName="Arial-Bold", fontSize=8.5, leading=11.5,
    textColor=colors.white,
))


def P(text, style="BodyVN"):
    return Paragraph(text, styles[style])


def bullet(text):
    return P(f"- {text}")


def header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#d9e2ec"))
    canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
    canvas.setFont("Arial", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9 * mm, "Hướng dẫn Admin - Danh sách cơ sở điều trị đột quỵ")
    canvas.drawRightString(width - 18 * mm, 9 * mm, f"Trang {doc.page}")
    canvas.restoreState()


class GuideDocTemplate(BaseDocTemplate):
    def __init__(self, filename):
        super().__init__(filename, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                         topMargin=21 * mm, bottomMargin=16 * mm, title="Hướng dẫn Admin cập nhật dữ liệu")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                      id="normal", topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="guide", frames=frame, onPage=header_footer)])


def table(data, widths, header=True, background=None):
    converted = []
    for row_index, row in enumerate(data):
        converted.append([
            P(str(cell), "TableHeadVN" if header and row_index == 0 else "TableVN")
            for cell in row
        ])
    t = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), BLUE))
    if background:
        commands.append(("BACKGROUND", (0, 1 if header else 0), (-1, -1), background))
    t.setStyle(TableStyle(commands))
    return t


story = []

# Cover
story += [Spacer(1, 21 * mm), P("HƯỚNG DẪN ADMIN", "CoverTitle"),
          P("Cập nhật và phát hành danh sách cơ sở<br/>điều trị đột quỵ", "CoverSub"),
          Spacer(1, 12 * mm),
          table([["Dành cho người quản trị Google Sheet", "Không cần biết lập trình"],
                 ["Khi nghi ngờ đột quỵ", "Gọi 115 ngay"]], [82 * mm, 82 * mm], background=LIGHT_BLUE),
          Spacer(1, 15 * mm), P("Bạn chỉ cần làm 4 việc", "H1VN")]
story.append(table([
    ["1", "Mở khóa chỉnh sửa", "Đổi ô E2 từ Released sang Updating."],
    ["2", "Nhập và kiểm tra", "Sửa dữ liệu trong các cột B đến I."],
    ["3", "Phát hành", "Sau khi kiểm tra, đổi E2 về Released."],
    ["4", "Xác nhận website", "Theo dõi GitHub Actions rồi tải lại website."],
], [12 * mm, 42 * mm, 110 * mm], header=False, background=LIGHT_BLUE))
story += [Spacer(1, 9 * mm), P("Hệ thống tự động làm phần còn lại", "H2VN"),
          P("Khi E2 chuyển sang Released, hệ thống tự tải Google Sheet, kiểm tra dữ liệu, cập nhật hospitals.json trên GitHub và triển khai lại GitHub Pages. Admin không cần chạy lệnh, sửa code hoặc nhờ IT cho mỗi lần cập nhật.")]
story.append(PageBreak())

# Page 2 input rules
story += [P("1. Nhập dữ liệu đúng cột", "H1VN"),
          P("Hàng 3 là tiêu đề. Dữ liệu bệnh viện bắt đầu từ hàng 4. Không đổi vị trí cột và không xóa hàng tiêu đề.")]
story.append(table([
    ["Cột", "Nội dung", "Cách nhập"],
    ["B", "Tên bệnh viện", "Viết đầy đủ, dễ tìm kiếm."],
    ["C", "Loại hình", "Ví dụ: Trung Tâm Đột Quỵ, Đơn vị Đột Quỵ."],
    ["D", "Địa chỉ", "Ghi địa chỉ đầy đủ và mới nhất."],
    ["E", "Hotline", "Chỉ dùng một trong hai format ở trang 3."],
    ["F/G", "Khả năng điều trị", "Chỉ chọn Có hoặc Không trong dropdown."],
    ["H", "Tỉnh/thành", "Dùng tên tỉnh thành thống nhất."],
    ["I", "Tọa độ", "Bắt buộc theo mẫu lat,lng."],
], [13 * mm, 39 * mm, 112 * mm]))
story += [P("Tọa độ là phần quan trọng", "H2VN"),
          P("Số trước dấu phẩy là lat (vĩ độ), số sau dấu phẩy là lng (kinh độ). Dùng dấu chấm cho số thập phân và chỉ dùng một dấu phẩy.", "BodyVN"),
          P("Đúng: 10.3872588,105.440206<br/>Sai: 105.440206,10.3872588", "CodeVN"),
          bullet("Nếu đổi địa chỉ, phải cập nhật tọa độ mới ở cột I."),
          bullet("Không nhập ghi chú hoặc dữ liệu cá nhân vào cột tọa độ."),
          bullet("Tên, loại hình, địa chỉ và tỉnh/thành không được để trống."),
          PageBreak()]

# Hotline page
story += [P("2. Quy tắc cột hotline", "H1VN"),
          P("Chỉ sử dụng hai format dưới đây. Dấu / có nghĩa là các số điện thoại độc lập; phần nhánh trong ngoặc chỉ là hướng dẫn nhấn tiếp.")]
story.append(table([
    ["Format", "Cách ghi", "Ý nghĩa khi bấm gọi"],
    ["1 - Nhiều số", "02838412692 / 115", "Có hai lựa chọn gọi: 02838412692 hoặc 115."],
    ["2 - Có nhánh", "02838412692 (nhấn 211) / 115", "Website gọi 02838412692; người dùng nhấn thêm 211, hoặc gọi 115."],
    ["Có nhánh bằng ext", "02839248158 (ext 440)", "Website gọi 02839248158; người dùng nhấn thêm 440."],
], [28 * mm, 61 * mm, 75 * mm], background=LIGHT_BLUE))
story += [P("Các lỗi thường gặp", "H2VN"),
          bullet("Dùng 'hoặc' thay cho '/': 02838412692 hoặc 115. Sửa thành: 02838412692 / 115."),
          bullet("Gộp nhánh vào số: 02838412692211. Sửa thành: 02838412692 (nhấn 211)."),
          bullet("Thiếu từ chỉ dẫn: 02838412692 (211). Sửa thành (nhấn 211) hoặc (ext 211)."),
          bullet("Ghi chú không phải nhánh: 02623841649 (Khoa cấp cứu). Hãy bỏ ghi chú hoặc đưa vào trường phù hợp."),
          bullet("Lẫn ký tự rác: ầ1n1 5T hhoặc 02933115. Xóa và nhập lại số chính xác."),
          bullet("Dùng dấu phẩy, chấm phẩy hoặc xuống dòng để tách số. Phải dùng dấu /."),
          Spacer(1, 3 * mm),
          P("Lưu ý: website không nối số nhánh vào liên kết gọi. Nếu hotline sai format, hệ thống sẽ chặn phát hành và báo dòng cần sửa.", "BodyVN"),
          PageBreak()]

# Release/troubleshooting
story += [P("3. Cập nhật, phát hành và xử lý lỗi", "H1VN"),
          P("E2 là nút an toàn của hệ thống. Chỉ khi E2 có giá trị Released thì dữ liệu mới được đưa lên website.", "BodyVN"),
          table([
              ["Bước", "Việc cần làm"],
              ["1", "Đổi E2 từ Released sang Updating trước khi sửa."],
              ["2", "Thêm hoặc sửa dữ liệu bệnh viện trong các cột B đến I."],
              ["3", "Kiểm tra hotline, dropdown Có/Không và lat,lng."],
              ["4", "Đổi E2 sang Released sau khi hoàn tất."],
              ["5", "Theo dõi Apps Script/GitHub Actions nếu cần, sau đó tải lại website."],
          ], [18 * mm, 146 * mm]),
          P("Trạng thái E2", "H2VN"),
          table([
              ["Thay đổi", "Kết quả"],
              ["Released -> Updating", "Không chạy đồng bộ; Admin được phép chỉnh sửa."],
              ["Updating -> Released", "Kích hoạt đồng bộ tự động nếu E2 được sửa trực tiếp trên Sheet."],
          ], [57 * mm, 107 * mm], background=LIGHT_BLUE),
          P("Nếu website chưa cập nhật", "H2VN"),
          bullet("Kiểm tra E2 có đúng chính tả Released không."),
          bullet("Mở Apps Script -> Executions để xem lỗi đồng bộ."),
          bullet("Mở GitHub -> Actions để xem workflow."),
          bullet("Tải lại bằng Ctrl + F5 hoặc mở cửa sổ riêng tư."),
          P("Checklist trước khi bấm Released", "H2VN"),
          bullet("C2 đúng dạng MM/YYYY."),
          bullet("Tên, loại hình, địa chỉ và tỉnh/thành đầy đủ."),
          bullet("Hotline đúng một trong hai format; không có lỗi nêu ở trang 3."),
          bullet("F/G chỉ có Có hoặc Không."),
          bullet("Cột I đúng thứ tự lat,lng; địa chỉ đổi đã có tọa độ mới."),
          bullet("Không có dữ liệu nhạy cảm hoặc dữ liệu nhập nhầm."),
          Spacer(1, 5 * mm),
          P("Google Sheet quản trị: docs.google.com/spreadsheets/d/1gkHumsymX037G_PjioUIoAIpnUnOvTqoI4TgSHd7H6c", "SmallVN"),
          P("Khi có tình huống y tế khẩn cấp, gọi 115. Website chỉ hỗ trợ tra cứu nhanh.", "SmallVN")]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
doc = GuideDocTemplate(str(OUTPUT))
doc.build(story)
print(OUTPUT)
