from app.models.image_metadata import ImageMetadata
from app.models.post import Post


def build_image_semantic_text(metadata: ImageMetadata) -> str:
    return "\n".join(
        (
            f"Subject: {metadata.subject}.",
            f"Category: {metadata.category}.",
            f"Caption: {metadata.caption}.",
            f"Tags: {', '.join(metadata.tags)}.",
            f"Attributes: {', '.join(metadata.attributes)}.",
            f"Objects: {', '.join(metadata.objects)}.",
        )
    )


def build_post_semantic_text(post: Post) -> str:
    lines = [f"Title: {post.title}.", f"Body: {post.body}."]
    if post.expected_subject is not None:
        lines.append(f"Expected subject: {post.expected_subject}.")
    if post.expected_category is not None:
        lines.append(f"Expected category: {post.expected_category}.")
    return "\n".join(lines)
