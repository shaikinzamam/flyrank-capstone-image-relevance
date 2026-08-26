"use client";

import Image, { type ImageProps } from "next/image";
import { useEffect, useState } from "react";
import { fetchImageContent } from "@/lib/api/images";

type AuthenticatedImageProps = Omit<
  ImageProps,
  "src" | "alt" | "loader" | "unoptimized"
> & {
  imageId: string;
  alt: string;
};

type PreviewState =
  | { status: "loading"; objectUrl: null }
  | { status: "ready"; objectUrl: string }
  | { status: "failed"; objectUrl: null };

export function AuthenticatedImage({
  imageId,
  alt,
  ...imageProps
}: AuthenticatedImageProps) {
  const [preview, setPreview] = useState<PreviewState>({
    status: "loading",
    objectUrl: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let createdUrl: string | null = null;

    // A changed image ID starts a new protected fetch and must not show old bytes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPreview({ status: "loading", objectUrl: null });
    void fetchImageContent(imageId, controller.signal)
      .then((blob) => {
        createdUrl = URL.createObjectURL(blob);
        if (active) {
          setPreview({ status: "ready", objectUrl: createdUrl });
        } else {
          URL.revokeObjectURL(createdUrl);
          createdUrl = null;
        }
      })
      .catch((reason: unknown) => {
        if (
          active &&
          !(reason instanceof DOMException && reason.name === "AbortError")
        ) {
          setPreview({ status: "failed", objectUrl: null });
        }
      });

    return () => {
      active = false;
      controller.abort();
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [imageId]);

  if (preview.status === "loading") {
    return (
      <div
        role="status"
        aria-label={`Loading ${alt}`}
        className="absolute inset-0 animate-pulse bg-slate-900"
      />
    );
  }
  if (preview.status === "failed") {
    return (
      <div
        role="img"
        aria-label={alt}
        className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-slate-950 p-4 text-center text-slate-400"
      >
        <span className="text-xs font-bold uppercase tracking-wider">
          Preview unavailable
        </span>
        <span className="line-clamp-2 text-sm">{alt}</span>
      </div>
    );
  }
  return (
    <Image
      {...imageProps}
      unoptimized
      src={preview.objectUrl}
      alt={alt}
    />
  );
}
