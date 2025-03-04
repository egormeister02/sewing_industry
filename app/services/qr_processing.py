from io import BytesIO
from PIL import Image
from pyzbar.pyzbar import decode
from PIL import Image, ImageDraw, ImageFont
import asyncio
import qrcode


async def generate_qr_code(data: dict) -> bytes:
    try:
        # Создаем QR-код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=0,
        )
        
        qr_data = (
            f"ID:  {data['batch_id']}\n"
            f"Проект: {data['project_name']}\n"
            f"Изделие: {data['product_name']}\n"
            f"Цвет: {data['color']}\n"
            f"Размер: {data['size']}\n"
            f"Количество: {data['quantity']}"
        )
        
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        loop = asyncio.get_event_loop()
        img_qr = await loop.run_in_executor(None, lambda: qr.make_image(fill_color='black', back_color='white'))
        
        # Создаем изображение для печати (4 * 6 см)
        # Переводим размеры в пиксели (предположим, что 1 см = 37.8 пикселей)
        width_px = int(4 * 37.8)
        height_px = int(6 * 37.8)
        img_print = Image.new('RGB', (width_px, height_px), 'white')
        
        # Вставляем QR-код в верхнюю часть изображения
        qr_size = round(width_px * 0.8)
        img_qr = img_qr.resize((qr_size, qr_size))
        img_print.paste(img_qr, ((width_px - qr_size) // 2, 10))
        
        # Добавляем текст под QR-кодом
        draw = ImageDraw.Draw(img_print)
        font = ImageFont.truetype("fonts/Arial.TTF", size=14) # Используем стандартный шрифт
        text_y = qr_size + 14
        for line in qr_data.split('\n'):
            draw.text((10, text_y), line, fill='black', font=font)
            text_y += 14  # Отступ между строками
        
        # Сохраняем изображение в байтовый массив
        img_byte_array = BytesIO()
        await loop.run_in_executor(None, img_print.rotate, 90)
        await loop.run_in_executor(None, img_print.save, img_byte_array, 'PDF')
        return img_byte_array.getvalue()
        
    except Exception as e:
        raise RuntimeError(f"Ошибка генерации изображения с QR-кодом и текстом: {str(e)}")


async def process_qr_code(image_data: bytes) -> str:
    try:
        loop = asyncio.get_event_loop()
        
        # Конвертируем байты в изображение с явным закрытием ресурса
        with await loop.run_in_executor(None, Image.open, BytesIO(image_data)) as img:
            # Конвертируем в черно-белый режим для лучшего распознавания
            grayscale = await loop.run_in_executor(None, lambda: img.convert('L'))
            
            # Пробуем разные методы декодирования
            decoded = await loop.run_in_executor(None, decode, grayscale)
            
            # Если не распознано, пробуем инвертировать цвета
            if not decoded:
                inverted = await loop.run_in_executor(None, lambda: Image.eval(grayscale, lambda x: 255 - x))
                decoded = await loop.run_in_executor(None, decode, inverted)

        if decoded:
            return decoded[0].data.decode('utf-8')
            
        return "QR-код не распознан"
        
    except Exception as e:
        return f"Ошибка обработки: {str(e)}"