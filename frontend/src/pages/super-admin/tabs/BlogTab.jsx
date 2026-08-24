import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Plus, Trash2, Pencil, ExternalLink, Eye, X, Check, FileText, Sparkles, Loader } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const emptyPost = {
  title: '', slug: '', excerpt: '', cover_image: '', body_md: '',
  tags: [], author: '', seo_title: '', seo_description: '', published: false,
};

export const BlogTab = ({ token }) => {
  const headers = { Authorization: `Bearer ${token}` };
  const [posts, setPosts] = useState([]);
  const [stats, setStats] = useState({ total: 0, published: 0, drafts: 0 });
  const [editing, setEditing] = useState(null);   // full post object being edited/created
  // iter-124: AI draft state — a lightweight side-modal that takes a
  // rough note + tone, calls /ai-draft, and fills the editor form.
  const [aiModal, setAiModal] = useState(false);
  const [aiNote, setAiNote] = useState('');
  const [aiTone, setAiTone] = useState('informative');
  const [aiLoading, setAiLoading] = useState(false);

  const load = async () => {
    try {
      const r = await axios.get(`${API}/super-admin/blog`, { headers });
      if (r.data?.success) {
        setPosts(r.data.data.posts || []);
        setStats(r.data.data.stats || { total: 0, published: 0, drafts: 0 });
      }
    } catch { toast.error('Failed to load blog posts'); }
  };
  useEffect(() => { load(); }, []);   // eslint-disable-line

  const startNew  = () => setEditing({ ...emptyPost, _new: true });
  const startEdit = async (post_id) => {
    try {
      const r = await axios.get(`${API}/super-admin/blog/${post_id}`, { headers });
      if (r.data?.success) setEditing({ ...r.data.data, tagsInput: (r.data.data.tags || []).join(', ') });
      else toast.error(r.data?.error || 'Failed to load post');
    } catch { toast.error('Failed to load post'); }
  };

  const save = async () => {
    if (!editing?.title?.trim()) { toast.error('Title is required'); return; }
    const payload = {
      ...editing,
      tags: (editing.tagsInput || (editing.tags || []).join(', ')).split(',').map(t => t.trim()).filter(Boolean),
    };
    delete payload.tagsInput;
    try {
      if (editing._new) {
        const r = await axios.post(`${API}/super-admin/blog`, payload, { headers });
        if (r.data?.success) { toast.success('Post created'); setEditing(null); load(); }
        else toast.error(r.data?.error || 'Failed');
      } else {
        const r = await axios.put(`${API}/super-admin/blog/${editing.post_id}`, payload, { headers });
        if (r.data?.success) { toast.success('Post saved'); setEditing(null); load(); }
        else toast.error(r.data?.error || 'Failed');
      }
    } catch (e) { toast.error(e.response?.data?.error || 'Save failed'); }
  };

  const removePost = async (post_id) => {
    if (!window.confirm('Delete this post permanently?')) return;
    try {
      const r = await axios.delete(`${API}/super-admin/blog/${post_id}`, { headers });
      if (r.data?.success) { toast.success('Deleted'); load(); }
      else toast.error(r.data?.error || 'Delete failed');
    } catch { toast.error('Delete failed'); }
  };

  const runAiDraft = async () => {
    if (!aiNote.trim() || aiNote.trim().length < 12) {
      toast.error('Give the AI at least a sentence or two to work with');
      return;
    }
    setAiLoading(true);
    try {
      const r = await axios.post(`${API}/super-admin/blog/ai-draft`, { note: aiNote.trim(), tone: aiTone }, { headers, timeout: 60000 });
      if (r.data?.success) {
        const d = r.data.data;
        // Fill the editor form. If no editor was open, open a NEW one
        // pre-filled with the AI response.
        setEditing((prev) => ({
          ...(prev || { _new: true }),
          title:            d.title,
          slug:             d.slug,
          excerpt:          d.excerpt,
          body_md:          d.body_md,
          tags:             d.tags || [],
          tagsInput:        (d.tags || []).join(', '),
          seo_title:        d.seo_title,
          seo_description: d.seo_description,
          published:        false,   // always land as draft — human review first
        }));
        setAiModal(false);
        setAiNote('');
        toast.success('AI draft ready — review and hit Save when it looks right');
      } else {
        toast.error(r.data?.error || 'AI draft failed');
      }
    } catch (e) {
      toast.error(e.response?.data?.error || e.message || 'AI draft failed');
    }
    setAiLoading(false);
  };

  return (
    <div data-testid="blog-tab">
      <div className="grid grid-cols-3 gap-3 mb-6">
        {[
          { label: 'Total Posts', value: stats.total, color: 'text-slate-800' },
          { label: 'Published',   value: stats.published, color: 'text-emerald-600' },
          { label: 'Drafts',      value: stats.drafts, color: 'text-amber-600' },
        ].map(c => (
          <div key={c.label} className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="text-xs text-slate-500">{c.label}</div>
            <div className={`text-xl font-bold ${c.color}`}>{c.value}</div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-900">Blog Posts</h2>
        <div className="flex items-center gap-2">
          <button onClick={() => setAiModal(true)}
            className="px-4 py-2 border border-violet-300 bg-violet-50 text-violet-700 rounded-lg text-sm font-medium hover:bg-violet-100 flex items-center gap-2"
            data-testid="ai-draft-btn">
            <Sparkles size={14} /> AI Draft
          </button>
          <button onClick={startNew} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-2" data-testid="new-blog-btn">
            <Plus size={14} /> New Post
          </button>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100" data-testid="blog-list">
        {posts.length === 0 && (
          <div className="p-12 text-center text-slate-400 text-sm">
            <FileText size={28} className="mx-auto mb-2 opacity-40" />
            No blog posts yet — click <b>New Post</b> to publish your first article.
          </div>
        )}
        {posts.map(p => (
          <div key={p.post_id} className="flex items-center gap-3 p-4" data-testid={`blog-row-${p.post_id}`}>
            {p.cover_image && <img src={p.cover_image} alt="" className="w-14 h-14 object-cover rounded-lg" />}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${p.published ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{p.published ? 'Published' : 'Draft'}</span>
                <span className="text-[11px] text-slate-400">by {p.author} · /{p.slug}</span>
              </div>
              <h3 className="font-medium text-slate-900 truncate">{p.title}</h3>
              <p className="text-xs text-slate-500 truncate">{p.excerpt}</p>
              <div className="flex items-center gap-1 mt-1">
                {(p.tags || []).slice(0, 4).map(t => (
                  <span key={t} className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">{t}</span>
                ))}
                <span className="text-[10px] text-slate-400 ml-2 flex items-center gap-1"><Eye size={10} /> {p.view_count || 0}</span>
              </div>
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              {p.published && (
                <a href={`/blog/${p.slug}`} target="_blank" rel="noreferrer"
                  className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Open live post">
                  <ExternalLink size={14} />
                </a>
              )}
              <button onClick={() => startEdit(p.post_id)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" data-testid={`edit-blog-${p.post_id}`}><Pencil size={14} /></button>
              <button onClick={() => removePost(p.post_id)} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg" data-testid={`delete-blog-${p.post_id}`}><Trash2 size={14} /></button>
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-auto" data-testid="blog-editor-modal" onClick={e => e.target === e.currentTarget && setEditing(null)}>
          <div className="bg-white rounded-xl w-full max-w-3xl p-6 my-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-slate-900">{editing._new ? 'New Blog Post' : 'Edit Post'}</h3>
              <div className="flex items-center gap-2">
                <button onClick={() => setAiModal(true)}
                  className="px-3 py-1.5 border border-violet-300 bg-violet-50 text-violet-700 rounded-lg text-xs font-medium hover:bg-violet-100 flex items-center gap-1.5"
                  data-testid="ai-draft-inline-btn">
                  <Sparkles size={12} /> AI Draft
                </button>
                <button onClick={() => setEditing(null)}><X size={18} className="text-slate-400" /></button>
              </div>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Title *</label>
                <input type="text" value={editing.title || ''} onChange={e => setEditing({ ...editing, title: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="blog-title-input" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Slug (optional)</label>
                  <input type="text" value={editing.slug || ''} onChange={e => setEditing({ ...editing, slug: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono" placeholder="auto-generated from title" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Author</label>
                  <input type="text" value={editing.author || ''} onChange={e => setEditing({ ...editing, author: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="FLOWRA Team" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Cover Image URL</label>
                <input type="url" value={editing.cover_image || ''} onChange={e => setEditing({ ...editing, cover_image: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="https://…" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Excerpt (max 280 chars)</label>
                <textarea rows={2} value={editing.excerpt || ''} onChange={e => setEditing({ ...editing, excerpt: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none" maxLength={280} />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Body (Markdown)</label>
                <textarea rows={10} value={editing.body_md || ''} onChange={e => setEditing({ ...editing, body_md: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono resize-y" placeholder="# Heading&#10;&#10;Body copy with **bold**, _italic_, [link](url), etc." data-testid="blog-body-input" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Tags (comma-separated)</label>
                <input type="text" value={editing.tagsInput ?? (editing.tags || []).join(', ')}
                  onChange={e => setEditing({ ...editing, tagsInput: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="tally, forecasting, product-update" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">SEO Title (≤70 chars)</label>
                  <input type="text" value={editing.seo_title || ''} onChange={e => setEditing({ ...editing, seo_title: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" maxLength={70} />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">SEO Description (≤160)</label>
                  <input type="text" value={editing.seo_description || ''} onChange={e => setEditing({ ...editing, seo_description: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" maxLength={160} />
                </div>
              </div>
              <label className="flex items-center gap-2 mt-2 cursor-pointer">
                <input type="checkbox" checked={!!editing.published} onChange={e => setEditing({ ...editing, published: e.target.checked })}
                  className="w-4 h-4" data-testid="blog-published-toggle" />
                <span className="text-sm text-slate-700">Published <span className="text-xs text-slate-400">(uncheck to keep as draft)</span></span>
              </label>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setEditing(null)} className="px-4 py-2 text-sm border border-slate-200 rounded-lg">Cancel</button>
              <button onClick={save} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-1" data-testid="blog-save-btn">
                <Check size={14} /> {editing._new ? 'Create Post' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* iter-124: AI Draft modal — uses GPT-5.2 via Emergent LLM key */}
      {aiModal && (
        <div className="fixed inset-0 bg-black/60 z-[60] flex items-center justify-center p-4" data-testid="ai-draft-modal"
             onClick={e => e.target === e.currentTarget && !aiLoading && setAiModal(false)}>
          <div className="bg-white rounded-xl w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
                <Sparkles size={18} className="text-violet-600" /> AI Draft with GPT-5.2
              </h3>
              <button onClick={() => !aiLoading && setAiModal(false)} disabled={aiLoading}><X size={18} className="text-slate-400" /></button>
            </div>
            <p className="text-xs text-slate-500 mb-4">
              Drop a rough note (1–3 sentences is enough). The AI turns it into a full FLOWRA-branded post — headings,
              tags, SEO title &amp; description — and lands it in the editor as a draft for you to review.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Rough note *</label>
                <textarea
                  rows={5}
                  value={aiNote}
                  onChange={e => setAiNote(e.target.value)}
                  disabled={aiLoading}
                  placeholder="e.g. Explain how demand forecasting helps a Diwali-season sweet-shop owner plan raw material buys 30 days ahead using Tally sync + FLOWRA's Wave 2 confidence bands."
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-violet-100"
                  data-testid="ai-draft-note-input"
                />
                <p className="text-[11px] text-slate-400 mt-1">{aiNote.length} chars (min 12)</p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Tone</label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { id: 'informative',      label: 'Informative' },
                    { id: 'casual',           label: 'Casual' },
                    { id: 'thought-leadership', label: 'Thought-Leadership' },
                  ].map(t => (
                    <button key={t.id} type="button" onClick={() => setAiTone(t.id)} disabled={aiLoading}
                      className={`px-3 py-1.5 text-xs rounded-lg border font-medium ${aiTone === t.id ? 'border-violet-500 bg-violet-50 text-violet-700' : 'border-slate-200 text-slate-500 hover:bg-slate-50'}`}
                      data-testid={`ai-tone-${t.id}`}>
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setAiModal(false)} disabled={aiLoading} className="px-4 py-2 text-sm border border-slate-200 rounded-lg disabled:opacity-50">
                Cancel
              </button>
              <button onClick={runAiDraft} disabled={aiLoading || aiNote.trim().length < 12}
                className="px-4 py-2 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 flex items-center gap-1.5"
                data-testid="ai-draft-run-btn">
                {aiLoading ? <><Loader className="animate-spin" size={14} /> Drafting…</> : <><Sparkles size={14} /> Generate Draft</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
