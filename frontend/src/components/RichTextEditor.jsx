import React, { useState, useCallback, useEffect } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Image from '@tiptap/extension-image';
import Link from '@tiptap/extension-link';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import Placeholder from '@tiptap/extension-placeholder';
import {
  Bold, Italic, Underline as UnderlineIcon, Heading1, Heading2, Heading3,
  List, ListOrdered, Quote, Code, Link as LinkIcon, Image as ImageIcon,
  AlignLeft, AlignCenter, AlignRight, Undo, Redo, Minus,
} from 'lucide-react';
import { ImageCropUpload } from './ImageCropUpload';

/*  Rich Text Editor for the Blog CMS. TipTap-based, tuned to output
 *  HTML that plays nicely with our public blog renderer.
 *
 *  - Toolbar: Bold, Italic, Underline, H1/H2/H3, lists, quote, code,
 *    link, image (via ImageCropUpload → Object Storage), alignment,
 *    undo/redo.
 *  - Inline images render with a width attribute; clicking one shows a
 *    small size popover (25 / 50 / 75 / 100%).
 */

// Extend Image so we persist a width % (used by the resize popover).
const ResizableImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      width: {
        default: '100%',
        renderHTML: (attrs) => ({ style: `width: ${attrs.width}` }),
        parseHTML: (el) => el.style.width || '100%',
      },
    };
  },
});

const TB = ({ active, disabled, onClick, title, children, testId }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    title={title}
    data-testid={testId}
    className={`p-1.5 rounded hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed
                ${active ? 'bg-slate-200 text-blue-700' : 'text-slate-600'}`}>
    {children}
  </button>
);

const Divider = () => <div className="w-px h-5 bg-slate-300 mx-1" />;

export const RichTextEditor = ({ value, onChange, token, placeholder }) => {
  const [imgModal, setImgModal]   = useState(false);
  const [showImgPop, setShowImgPop] = useState(false);
  const [selectedImgWidth, setSelectedImgWidth] = useState('100%');

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
      Underline,
      Link.configure({ openOnClick: false, autolink: true, HTMLAttributes: { class: 'text-blue-600 underline' } }),
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      ResizableImage.configure({ inline: false, HTMLAttributes: { class: 'rounded-lg my-4 mx-auto block' } }),
      Placeholder.configure({ placeholder: placeholder || 'Start writing your post…' }),
    ],
    content: value || '',
    onUpdate: ({ editor: ed }) => onChange?.(ed.getHTML()),
    editorProps: {
      attributes: {
        class: 'prose prose-slate max-w-none min-h-[300px] px-4 py-3 focus:outline-none',
        'data-testid': 'rich-editor-content',
      },
    },
  });
  // Sync when parent replaces the value programmatically (e.g. AI draft
  // populated → set into the editor without wiping the user's caret).
  useEffect(() => {
    if (!editor) return;
    if (value !== undefined && value !== null && value !== editor.getHTML()) {
      editor.commands.setContent(value || '', { emitUpdate: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, editor]);

  // Track selection so the image-resize popover appears only when an
  // image node is selected.
  useEffect(() => {
    if (!editor) return;
    const sync = () => {
      const isImg = editor.isActive('image');
      setShowImgPop(isImg);
      if (isImg) setSelectedImgWidth(editor.getAttributes('image').width || '100%');
    };
    editor.on('selectionUpdate', sync);
    editor.on('transaction', sync);
    return () => { editor.off('selectionUpdate', sync); editor.off('transaction', sync); };
  }, [editor]);

  const setImageWidth = (w) => {
    if (!editor) return;
    editor.chain().focus().updateAttributes('image', { width: w }).run();
    setSelectedImgWidth(w);
  };

  const addLink = useCallback(() => {
    if (!editor) return;
    const prev = editor.getAttributes('link').href || '';
    // eslint-disable-next-line no-alert
    const url = window.prompt('Enter URL (leave empty to remove)', prev);
    if (url === null) return;
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  }, [editor]);

  const onImageUploaded = ({ url }) => {
    if (!editor) return;
    editor.chain().focus().setImage({ src: url, width: '100%' }).run();
  };

  if (!editor) return null;

  return (
    <div className="border border-slate-200 rounded-lg bg-white flex flex-col" data-testid="rich-text-editor">
      {/* Toolbar — sticks to the top of the editor frame so it stays
          visible even after the content grows past the frame height. */}
      <div className="flex flex-wrap items-center gap-0.5 px-2 py-1.5 border-b border-slate-200 bg-slate-50 rounded-t-lg sticky top-0 z-10">
        <TB testId="rte-bold"   title="Bold (Ctrl+B)"  active={editor.isActive('bold')}   onClick={() => editor.chain().focus().toggleBold().run()}><Bold size={14} /></TB>
        <TB testId="rte-italic" title="Italic (Ctrl+I)" active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}><Italic size={14} /></TB>
        <TB testId="rte-underline" title="Underline (Ctrl+U)" active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()}><UnderlineIcon size={14} /></TB>
        <Divider />
        <TB testId="rte-h1" title="Heading 1" active={editor.isActive('heading', { level: 1 })} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}><Heading1 size={14} /></TB>
        <TB testId="rte-h2" title="Heading 2" active={editor.isActive('heading', { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}><Heading2 size={14} /></TB>
        <TB testId="rte-h3" title="Heading 3" active={editor.isActive('heading', { level: 3 })} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}><Heading3 size={14} /></TB>
        <Divider />
        <TB testId="rte-ul" title="Bullet list" active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}><List size={14} /></TB>
        <TB testId="rte-ol" title="Numbered list" active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()}><ListOrdered size={14} /></TB>
        <TB testId="rte-quote" title="Blockquote" active={editor.isActive('blockquote')} onClick={() => editor.chain().focus().toggleBlockquote().run()}><Quote size={14} /></TB>
        <TB testId="rte-code" title="Code block" active={editor.isActive('codeBlock')} onClick={() => editor.chain().focus().toggleCodeBlock().run()}><Code size={14} /></TB>
        <TB testId="rte-hr" title="Horizontal rule" onClick={() => editor.chain().focus().setHorizontalRule().run()}><Minus size={14} /></TB>
        <Divider />
        <TB testId="rte-align-left" title="Align left" active={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()}><AlignLeft size={14} /></TB>
        <TB testId="rte-align-center" title="Align center" active={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()}><AlignCenter size={14} /></TB>
        <TB testId="rte-align-right" title="Align right" active={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()}><AlignRight size={14} /></TB>
        <Divider />
        <TB testId="rte-link"  title="Link"  active={editor.isActive('link')}  onClick={addLink}><LinkIcon size={14} /></TB>
        <TB testId="rte-image" title="Insert image" onClick={() => setImgModal(true)}><ImageIcon size={14} /></TB>
        <div className="flex-1" />
        <TB testId="rte-undo" title="Undo" disabled={!editor.can().undo()} onClick={() => editor.chain().focus().undo().run()}><Undo size={14} /></TB>
        <TB testId="rte-redo" title="Redo" disabled={!editor.can().redo()} onClick={() => editor.chain().focus().redo().run()}><Redo size={14} /></TB>
      </div>

      {/* Image resize popover — appears when an image is selected. */}
      {showImgPop && (
        <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 border-b border-blue-200 text-xs"
             data-testid="image-resize-popover">
          <span className="text-blue-800 font-medium">Image size:</span>
          {[
            { label: 'S', w: '25%' }, { label: 'M', w: '50%' },
            { label: 'L', w: '75%' }, { label: 'Full', w: '100%' },
          ].map(o => (
            <button
              key={o.w}
              type="button"
              onClick={() => setImageWidth(o.w)}
              data-testid={`img-size-${o.label.toLowerCase()}`}
              className={`px-2 py-0.5 rounded border font-medium ${selectedImgWidth === o.w ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-blue-700 border-blue-300 hover:bg-blue-100'}`}>
              {o.label}
            </button>
          ))}
          <span className="text-blue-600 ml-2">({selectedImgWidth})</span>
        </div>
      )}

      <div className="max-h-[400px] overflow-y-auto" data-testid="rich-editor-scroll">
        <EditorContent editor={editor} />
      </div>

      <ImageCropUpload
        open={imgModal}
        onClose={() => setImgModal(false)}
        onUploaded={onImageUploaded}
        token={token}
      />
    </div>
  );
};

export default RichTextEditor;
