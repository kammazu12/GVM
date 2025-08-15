import os
import uuid
from flask import current_app
from PIL import Image
import pillow_heif


def save_uploaded_image(file, subfolder, prefix="file_", allowed_extensions=None):
    """
    Feltöltött kép mentése egy adott mappába.

    :param file: Feltöltött fájl objektum (werkzeug.datastructures.FileStorage)
    :param subfolder: Mappa neve a static/uploads alatt (pl. 'company_logos', 'profile_pictures')
    :param prefix: Fájlnév előtag
    :param allowed_extensions: Engedélyezett kiterjesztések listája
    :return: (success, filename_or_error)
    """
    if not file:
        return False, "Nincs fájl kiválasztva."

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if allowed_extensions and ext not in allowed_extensions:
        return False, "Érvénytelen fájlformátum."

    filename = f"{prefix}{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(current_app.root_path, 'static/uploads', subfolder)
    os.makedirs(save_path, exist_ok=True)

    try:
        if ext == 'heic':
            heif_image = pillow_heif.read_heif(file)
            image = Image.frombytes(heif_image.mode, heif_image.size, heif_image.data)
            filename = filename.rsplit('.', 1)[0] + '.jpg'
            image.save(os.path.join(save_path, filename), format='JPEG')
        else:
            file.save(os.path.join(save_path, filename))
    except Exception as e:
        return False, f"Hiba a mentés közben: {str(e)}"

    return True, filename
