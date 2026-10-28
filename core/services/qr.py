"""Código QR para abrir la aplicación desde el celular (página /qr/ y comando generar_qr)."""

import io

import qrcode
import qrcode.image.pure
import qrcode.image.svg


def _qr(url: str) -> qrcode.QRCode:
    codigo = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    codigo.add_data(url)
    codigo.make(fit=True)
    return codigo


def qr_svg(url: str) -> str:
    """SVG listo para incrustar en una página (escala sin perder nitidez)."""
    imagen = _qr(url).make_image(image_factory=qrcode.image.svg.SvgPathImage)
    return imagen.to_string(encoding="unicode")


def qr_png(url: str) -> bytes:
    """PNG para diapositivas o para imprimir."""
    salida = io.BytesIO()
    # PyPNG es Python puro: no hace falta instalar Pillow.
    _qr(url).make_image(image_factory=qrcode.image.pure.PyPNGImage).save(salida)
    return salida.getvalue()
