"""Fotografar a janela da plataforma e traduzir toque em clique.

Por que isto existe: escolher o perfil da Netflix pelo touchpad é mirar um
cursor invisível numa tela que está do outro lado da sala. O mesmo vale para a
tela de login, que foi a reclamação original — o controle abria o serviço e
largava a pessoa ali.

A saída é uma foto e uma conta. A foto é um quadro da janela; a conta converte
onde o dedo tocou na imagem para onde o mouse precisa ir na tela. Nada de ler
o HTML da página: não depende de navegador com porta de depuração aberta, não
quebra quando a Netflix muda o site, e funciona igual nos seis serviços.

Medido nesta máquina, janela do Chrome em 1920x1080:

    PrintWindow sem flag ......... 100% preto
    PrintWindow + FULLCONTENT .... conteúdo real, 60 ms
    BitBlt da janela ............. 100% preto
    BitBlt da tela ............... funciona, mas copia o que estiver por cima

Só o segundo serve. O primeiro e o terceiro voltam pretos porque o Chrome
desenha por aceleração de hardware, e a composição não passa pelo GDI.
"""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
import io
import sys
from ctypes import wintypes

from app.windows.focus import DesktopWindow


# Sem esta flag o Chrome devolve um retângulo preto. Ela pede à janela que se
# desenhe inteira, inclusive a parte composta fora do GDI.
PW_RENDERFULLCONTENT = 0x00000002
BI_RGB = 0
DIB_RGB_COLORS = 0

# 960 de largura e qualidade 70: medido em 44 KB no caso mais pesado que existe
# aqui — um quadro de vídeo em movimento, que é ruído puro. Tela de perfil é
# interface chapada e comprime bem melhor. Na rede local isso chega instantâneo,
# e subir para 1280 dobraria o peso sem mudar o que dá para enxergar no celular.
LARGURA_MAXIMA = 960
QUALIDADE = 70

# Lado do recorte do avatar, em fração da largura da janela. O avatar da Netflix
# ocupa perto disso; um pouco a mais só entrega fundo em volta, que é inofensivo.
LADO_DO_AVATAR = 0.11


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


@dataclass(frozen=True)
class Retangulo:
    esquerda: int
    topo: int
    largura: int
    altura: int


@dataclass(frozen=True)
class Quadro:
    """Um instante da janela, já no tamanho que vai para o celular."""

    jpeg: bytes
    largura: int
    altura: int


def ponto_na_tela(rect: Retangulo, x: float, y: float) -> tuple[int, int]:
    """Onde o dedo tocou, em coordenada de tela.

    As frações são relativas à janela, não à tela: assim o cadastro de um perfil
    continua valendo depois de mover ou redimensionar a janela, que é o caso
    normal de quem usa o navegador. Guardar pixel absoluto quebraria no primeiro
    arrasto.

    Fora do intervalo o valor é preso na borda em vez de recusado — a origem
    disso é um dedo num retângulo, e um arredondamento a mais não pode virar
    erro na cara do usuário. O que não pode é o clique escapar da janela.
    """
    x_preso = min(1.0, max(0.0, x))
    y_preso = min(1.0, max(0.0, y))
    # -1 para o extremo 1.0 cair no último pixel de dentro, e não no primeiro
    # pixel de fora — que na borda direita seria a janela vizinha.
    return (
        rect.esquerda + min(rect.largura - 1, int(x_preso * rect.largura)),
        rect.topo + min(rect.altura - 1, int(y_preso * rect.altura)),
    )


def _recorte_do_avatar(rect_largura: int, rect_altura: int, x: float, y: float) -> tuple[int, int, int, int]:
    """Caixa quadrada em volta do toque, presa dentro da imagem."""
    lado = max(24, int(rect_largura * LADO_DO_AVATAR))
    centro_x = int(min(1.0, max(0.0, x)) * rect_largura)
    centro_y = int(min(1.0, max(0.0, y)) * rect_altura)
    esquerda = min(max(0, centro_x - lado // 2), max(0, rect_largura - lado))
    topo = min(max(0, centro_y - lado // 2), max(0, rect_altura - lado))
    return esquerda, topo, esquerda + min(lado, rect_largura), topo + min(lado, rect_altura)


class WindowCapture:
    """Um quadro da janela, sob demanda.

    Sob demanda e nunca em laço: isto é uma foto quando alguém pede, não uma
    transmissão da tela. Um quadro por toque mantém o custo perto de zero e a
    promessa fácil de explicar.
    """

    def __init__(
        self,
        largura_maxima: int = LARGURA_MAXIMA,
        qualidade: int = QUALIDADE,
    ) -> None:
        self._largura_maxima = largura_maxima
        self._qualidade = qualidade

    def retangulo(self, janela: DesktopWindow) -> Retangulo | None:
        if sys.platform != "win32":
            return None
        rect = wintypes.RECT()
        try:
            if not ctypes.windll.user32.GetWindowRect(janela.handle, ctypes.byref(rect)):
                return None
        except OSError:
            return None
        largura = rect.right - rect.left
        altura = rect.bottom - rect.top
        if largura <= 0 or altura <= 0:
            return None
        return Retangulo(rect.left, rect.top, largura, altura)

    def _imagem(self, janela: DesktopWindow, rect: Retangulo):
        """A janela como imagem do Pillow, ou None se a captura falhou."""
        try:
            from PIL import Image
        except ImportError:
            # Sem Pillow o resto do controle segue igual: só esta tela some.
            return None

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        hdc_janela = user32.GetWindowDC(janela.handle)
        if not hdc_janela:
            return None
        hdc_memoria = gdi32.CreateCompatibleDC(hdc_janela)
        bitmap = gdi32.CreateCompatibleBitmap(hdc_janela, rect.largura, rect.altura)
        anterior = gdi32.SelectObject(hdc_memoria, bitmap)
        try:
            if not user32.PrintWindow(janela.handle, hdc_memoria, PW_RENDERFULLCONTENT):
                return None

            cabecalho = _BITMAPINFOHEADER()
            cabecalho.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
            cabecalho.biWidth = rect.largura
            # Negativo: linhas de cima para baixo, na ordem em que a imagem é
            # lida. Positivo devolveria de cabeça para baixo.
            cabecalho.biHeight = -rect.altura
            cabecalho.biPlanes = 1
            cabecalho.biBitCount = 32
            cabecalho.biCompression = BI_RGB

            buffer = ctypes.create_string_buffer(rect.largura * rect.altura * 4)
            if not gdi32.GetDIBits(
                hdc_memoria, bitmap, 0, rect.altura, buffer,
                ctypes.byref(cabecalho), DIB_RGB_COLORS,
            ):
                return None
            return Image.frombuffer(
                "RGBA", (rect.largura, rect.altura), buffer.raw, "raw", "BGRA", 0, 1,
            ).convert("RGB")
        except OSError:
            return None
        finally:
            gdi32.SelectObject(hdc_memoria, anterior)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(hdc_memoria)
            user32.ReleaseDC(janela.handle, hdc_janela)

    def capturar(self, janela: DesktopWindow) -> Quadro | None:
        rect = self.retangulo(janela)
        if rect is None:
            return None
        imagem = self._imagem(janela, rect)
        if imagem is None:
            return None

        if imagem.width > self._largura_maxima:
            altura = round(imagem.height * self._largura_maxima / imagem.width)
            imagem = imagem.resize((self._largura_maxima, altura))

        return Quadro(self._para_jpeg(imagem), imagem.width, imagem.height)

    def recortar_avatar(self, janela: DesktopWindow, x: float, y: float) -> bytes | None:
        """Um quadrado em volta do ponto tocado, em tamanho de ícone.

        Sai da mesma foto que a pessoa acabou de ver, então o avatar no controle
        é literalmente o avatar do serviço — não um desenho parecido.
        """
        rect = self.retangulo(janela)
        if rect is None:
            return None
        imagem = self._imagem(janela, rect)
        if imagem is None:
            return None
        recorte = imagem.crop(_recorte_do_avatar(imagem.width, imagem.height, x, y))
        if recorte.width > 160:
            recorte = recorte.resize((160, 160))
        return self._para_jpeg(recorte)

    def _para_jpeg(self, imagem) -> bytes:
        buffer = io.BytesIO()
        imagem.save(buffer, "JPEG", quality=self._qualidade)
        return buffer.getvalue()
