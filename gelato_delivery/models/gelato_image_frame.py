import base64
import io
import logging

from PIL import Image

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class GelatoImageFrame(models.AbstractModel):
    """How a product photo sits in its frame on the website.

    Every card has the same frame so the rows line up, but photos do not
    all have the same shape. A square photo of a thermal box fills it
    nicely; a tall bottle of prosecco filled the same way gets its neck
    and its base cut off. Rather than making the shop crop pictures
    before uploading them, these two settings say what to do with what
    they have.
    """

    _name = "gelato.image.frame"
    _description = "Photo framing on the website"

    image_fit = fields.Selection(
        selection=[
            ("cover", "Fill the frame (crops the edges)"),
            ("contain", "Whole photo (leaves space around it)"),
        ],
        string="Photo in the frame",
        default="cover",
        required=True,
        help="Fill the frame looks best for a photo shot square. Choose "
        "the whole photo for a tall bottle or anything that must not be "
        "cut off.",
    )
    image_focus = fields.Selection(
        selection=[
            ("top", "Top"),
            ("center", "Middle"),
            ("bottom", "Bottom"),
        ],
        string="Keep in view",
        default="center",
        required=True,
        help="Which part of the photo to keep when the frame crops it. "
        "Has no effect when the whole photo is shown.",
    )

    def image_style(self):
        """The inline style for the <img> on the card."""
        self.ensure_one()
        return "object-fit: %s; object-position: center %s;" % (
            self.image_fit or "cover",
            self.image_focus or "center",
        )

    # ------------------------------------------------------------------
    # Keeping photos light
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("image"):
                vals["image"] = self._shrink_photo(vals["image"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("image"):
            vals = dict(vals, image=self._shrink_photo(vals["image"]))
        return super().write(vals)

    @staticmethod
    def _shrink_photo(image):
        """Re-encode an uploaded photo as WebP.

        A phone photo saved as PNG stays PNG, and PNG is the worst thing
        to store a photograph in: one thumbnail of a bottle came to
        184 kB and took half a minute to reach a phone abroad. WebP keeps
        transparency, so a cut-out product still works, and the same
        picture lands at a fraction of the size.

        WebP would be smaller still, but this Pillow reports support and
        then has no encoder for it, so a picture with transparency stays
        PNG - a cut-out product needs its background - and everything
        else becomes JPEG.

        Anything that cannot be converted is stored as it came: a photo
        that is merely heavy beats no photo at all.
        """
        try:
            raw = base64.b64decode(image)
            picture = Image.open(io.BytesIO(raw))
            picture.load()
            transparent = picture.mode in ("RGBA", "LA", "P") and (
                "transparency" in picture.info or picture.mode in ("RGBA", "LA")
            )
            picture = picture.convert("RGBA" if transparent else "RGB")
            picture.thumbnail((1024, 1024), Image.LANCZOS)

            out = io.BytesIO()
            if transparent:
                picture.save(out, format="PNG", optimize=True)
            else:
                picture.save(out, format="JPEG", quality=82, optimize=True,
                             progressive=True)
            shrunk = out.getvalue()
            if len(shrunk) >= len(raw):
                # Already lighter than anything we would make of it.
                return image
            return base64.b64encode(shrunk)
        except Exception:
            _logger.warning("Could not re-encode a product photo", exc_info=True)
            return image
