from io import BytesIO
from PIL import Image
from pyzbar.pyzbar import decode
import asyncio
import qrcode

async def generate_qr_code(data: dict) -> bytes:
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        qr_data = (
            f"ID:  {data['batch_id']}\n"
            f"Проект: {data['project_name']}\n"
            f"Изделие: {data['product_name']}\n"
            f"Цвет: {data['color']}\n"
            f"Размер: {data['size']}\n"
            f"Количество: {data['quantity']}\n"
            f"Детали: {data['parts_count']}"
        )
        
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        loop = asyncio.get_event_loop()
        # Исправляем вызов run_in_executor
        img = await loop.run_in_executor(None, lambda: qr.make_image(fill_color='black', back_color='white'))
        
        img_byte_array = BytesIO()
        await loop.run_in_executor(None, img.save, img_byte_array, 'PNG')
        return img_byte_array.getvalue()
        
    except Exception as e:
        raise RuntimeError(f"Ошибка генерации QR-кода: {str(e)}")


async def process_qr_code(image_data: bytes) -> str:
    """
    Асинхронно обрабатывает изображение с QR-кодом.
    
    :param image_data: Байты изображения
    :return: Декодированный текст из QR-кода или сообщение об ошибке
    """
    try:
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(None, Image.open, BytesIO(image_data))
        decoded = await loop.run_in_executor(None, decode, image)
        return decoded[0].data.decode('utf-8') if decoded else "QR-код не распознан"
    except IndexError:
        return "QR-код не распознан"
    except Exception as e:
        return f"Ошибка обработки: {str(e)}"