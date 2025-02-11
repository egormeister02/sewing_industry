from io import BytesIO
from PIL import Image
from pyzbar.pyzbar import decode
import asyncio

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