import uuid
from django import template

register = template.Library()


@register.inclusion_tag("components/image_carousel.html")
def image_carousel(
    images,
    carousel_id=None,
    aspect_ratio="16by9",
    show_nav=True,
    show_dots=True,
    aria_label="Image carousel",
    items_mobile=1,
    items_tablet=2,
    items_desktop=3,
    gap="0.75rem",
    autoplay=False,
    interval=5000,          # ms
    loop=True,
    pause_on_hover=True,
):
    return {
        "carousel_id": carousel_id or f"bc-{uuid.uuid4().hex}",
        "images": images,
        "aspect_ratio": aspect_ratio,
        "show_nav": show_nav,
        "show_dots": show_dots,
        "aria_label": aria_label,
        "items_mobile": items_mobile,
        "items_tablet": items_tablet,
        "items_desktop": items_desktop,
        "gap": gap,
        "autoplay": autoplay,
        "interval": interval,
        "loop": loop,
        "pause_on_hover": pause_on_hover,
    }
