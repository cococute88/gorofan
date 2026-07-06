"use client";

import StarterKit from "@tiptap/starter-kit";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import { forwardRef, useEffect, useImperativeHandle } from "react";

export interface TipTapHandle {
  /** Append plain text (used for streaming AI insertion). */
  appendText: (text: string) => void;
  getText: () => string;
  getJSON: () => unknown;
  focusEnd: () => void;
  editor: Editor | null;
}

/**
 * Rich-text chapter editor (design 7, 11.6). TipTap StarterKit.
 * Streaming AI tokens are appended at the document end via `appendText`.
 */
export const TipTapEditor = forwardRef<
  TipTapHandle,
  {
    initialText?: string;
    onChange?: (text: string, json: unknown) => void;
    editable?: boolean;
  }
>(function TipTapEditor({ initialText = "", onChange, editable = true }, ref) {
  const editor = useEditor({
    extensions: [StarterKit],
    // Avoid SSR hydration mismatch in Next App Router.
    immediatelyRender: false,
    editable,
    content: textToDoc(initialText),
    editorProps: {
      attributes: {
        class:
          "prose prose-sm dark:prose-invert max-w-none min-h-[50vh] focus:outline-none",
      },
    },
    onUpdate: ({ editor: e }) => {
      onChange?.(e.getText(), e.getJSON());
    },
  });

  // Keep external editability in sync.
  useEffect(() => {
    editor?.setEditable(editable);
  }, [editor, editable]);

  useImperativeHandle(
    ref,
    () => ({
      appendText: (text: string) => {
        if (!editor) return;
        editor.commands.focus("end");
        editor.commands.insertContent(text.replace(/\n/g, "<br>"));
      },
      getText: () => editor?.getText() ?? "",
      getJSON: () => editor?.getJSON() ?? {},
      focusEnd: () => editor?.commands.focus("end"),
      editor,
    }),
    [editor],
  );

  return <EditorContent editor={editor} />;
});

function textToDoc(text: string) {
  if (!text) return "<p></p>";
  return text
    .split(/\n{2,}/)
    .map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
