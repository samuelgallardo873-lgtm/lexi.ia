"""
LexBot - Piezas visuales reutilizables.

Acá viven el logo de la balanza y el avatar del profesional, que se dibujan
con vectores en lugar de depender de archivos de imagen: así la app no
necesita empaquetar íconos ni la librería Pillow para arrancar.
"""

import customtkinter as ctk

from theme import C, R, T, fuente, mono

# Pillow es opcional: solo hace falta si el abogado carga una foto propia.
try:
    from PIL import Image, ImageDraw
    HAY_PILLOW = True
except ImportError:
    HAY_PILLOW = False


class LogoBalanza(ctk.CTkCanvas):
    """Balanza de la justicia dibujada con líneas; escala con el tamaño pedido."""

    def __init__(self, master, lado=34, color=None, fondo=None):
        fondo = fondo or C["sidebar"]
        super().__init__(master, width=lado, height=lado, bg=fondo,
                         highlightthickness=0, bd=0)
        color = color or C["gold"]
        u = lado / 34.0                      # unidad de escala sobre el diseño base
        cx = lado / 2
        grosor = max(1, round(1.6 * u))

        # Mástil y base
        self.create_line(cx, 7 * u, cx, 26 * u, fill=color, width=grosor)
        self.create_line(cx - 6 * u, 27 * u, cx + 6 * u, 27 * u, fill=color,
                         width=grosor, capstyle="round")
        self.create_line(cx - 3 * u, 26 * u, cx + 3 * u, 26 * u, fill=color, width=grosor)

        # Brazo y nudo superior
        self.create_line(cx - 11 * u, 11 * u, cx + 11 * u, 11 * u, fill=color,
                         width=grosor, capstyle="round")
        self.create_oval(cx - 2 * u, 5 * u, cx + 2 * u, 9 * u, outline=color,
                         width=grosor)

        # Platillos: dos cuencos colgando del brazo
        for lado_x in (-11 * u, 11 * u):
            x = cx + lado_x
            self.create_line(x, 11 * u, x, 15 * u, fill=color, width=max(1, grosor - 1))
            self.create_arc(x - 6 * u, 12 * u, x + 6 * u, 21 * u, start=180, extent=180,
                            style="arc", outline=color, width=grosor)


class Avatar(ctk.CTkFrame):
    """
    Foto del profesional, o sus iniciales si todavía no cargó ninguna.

    La foto se recorta en círculo. Si Pillow no está instalado o la ruta no
    existe, se muestran las iniciales sin que la app falle.
    """

    def __init__(self, master, iniciales="LB", foto="", lado=46, fondo=None):
        super().__init__(master, width=lado, height=lado, corner_radius=lado // 2,
                         fg_color=fondo or C["accent_soft"])
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        imagen = self._cargar_foto(foto, lado)
        if imagen is not None:
            ctk.CTkLabel(self, text="", image=imagen).grid(row=0, column=0)
        else:
            ctk.CTkLabel(self, text=iniciales, font=fuente(T.meta, "bold"),
                         text_color=C["cyan"]).grid(row=0, column=0)

    @staticmethod
    def _cargar_foto(ruta, lado):
        if not ruta or not HAY_PILLOW:
            return None
        try:
            original = Image.open(ruta).convert("RGBA")
        except (OSError, ValueError):
            return None

        # Recorte cuadrado centrado y luego máscara circular.
        corto = min(original.size)
        izq = (original.width - corto) // 2
        arriba = (original.height - corto) // 2
        recorte = original.crop((izq, arriba, izq + corto, arriba + corto))
        recorte = recorte.resize((lado, lado), Image.LANCZOS)

        mascara = Image.new("L", (lado, lado), 0)
        ImageDraw.Draw(mascara).ellipse((0, 0, lado - 1, lado - 1), fill=255)
        recorte.putalpha(mascara)
        return ctk.CTkImage(light_image=recorte, dark_image=recorte, size=(lado, lado))


def chip(master, texto, color_texto=None, color_fondo=None, alto=24):
    """Insignia compacta en mayúsculas monoespaciadas."""
    return ctk.CTkLabel(master, text=f" {texto} ",
                        fg_color=color_fondo or C["card_row"], corner_radius=R.chip,
                        height=alto, text_color=color_texto or C["muted"],
                        font=mono(T.etiqueta, "bold"))


def punto(master, color, lado=8):
    """Punto de color para estados y leyendas."""
    return ctk.CTkFrame(master, width=lado, height=lado, corner_radius=lado // 2,
                        fg_color=color)
