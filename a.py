import qrcode
from PIL import Image

def generate_qr_with_logo(url, logo_path, output_path):
    # 1. Khởi tạo đối tượng QRCode
    qr = qrcode.QRCode(
        version=1,
        # Sử dụng ERROR_CORRECT_H (khả năng sửa lỗi 30%) để QR vẫn quét được khi bị chèn logo ở giữa
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    
    # 2. Thêm dữ liệu đường dẫn
    qr.add_data(url)
    qr.make(fit=True)

    # 3. Tạo ảnh QR (màu đen nền trắng)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # 4. Mở hình logo
    logo = Image.open(logo_path)

    # 5. Tính toán kích thước cho logo (khoảng 1/4 đến 1/5 chiều rộng của mã QR)
    qr_width, qr_height = qr_img.size
    logo_max_size = qr_width // 4

    # Thay đổi kích thước logo giữ nguyên tỷ lệ
    logo.thumbnail((logo_max_size, logo_max_size), Image.Resampling.LANCZOS)

    # 6. Tính vị trí đặt logo vào chính giữa mã QR
    logo_w, logo_h = logo.size
    pos_x = (qr_width - logo_w) // 2
    pos_y = (qr_height - logo_h) // 2

    # 7. Chèn logo vào hình QR
    # Nếu logo có kênh Alpha (trong suốt), dùng logo làm mask
    if logo.mode == 'RGBA':
        qr_img.paste(logo, (pos_x, pos_y), logo)
    else:
        qr_img.paste(logo, (pos_x, pos_y))

    # 8. Lưu kết quả
    qr_img.save(output_path)
    print(f"Mã QR đã được tạo thành công tại: {output_path}")

# Chạy hàm tạo mã QR
if __name__ == "__main__":
    target_url = "https://adq.io.vn"
    logo_filename = "logo.png"  # Đường dẫn đến file logo của bạn
    output_filename = "adq_qr_code.png"
    
    generate_qr_with_logo(target_url, logo_filename, output_filename)