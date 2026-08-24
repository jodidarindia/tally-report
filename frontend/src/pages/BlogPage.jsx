import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowLeft, Calendar, Tag, ChevronRight } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

/* Very small MD → HTML converter (headings, bold, italic, links, code,
 * lists) so we don't drag in a dependency for a first-cut blog. */
const renderMd = (md = '') => {
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  let html = esc(md);
  html = html.replace(/^### (.*)$/gm, '<h3>$1</h3>')
             .replace(/^## (.*)$/gm, '<h2>$1</h2>')
             .replace(/^# (.*)$/gm, '<h1>$1</h1>');
  html = html.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
             .replace(/\*(.*?)\*/g, '<i>$1</i>')
             .replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-[#0052FF] underline" target="_blank" rel="noreferrer">$1</a>');
  html = html.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>')
             .replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
  html = html.replace(/\n\n/g, '</p><p>');
  return `<div class="prose"><p>${html}</p></div>`;
};

export const BlogListPage = ({ onNavigate, initialSlug = '' }) => {
  const [posts, setPosts] = useState([]);
  const [tags, setTags] = useState([]);
  const [activeTag, setActiveTag] = useState('');
  const [loading, setLoading] = useState(true);
  const [activePost, setActivePost] = useState(null);

  const load = async (tag = '') => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/public/blog${tag ? `?tag=${encodeURIComponent(tag)}` : ''}`);
      if (r.data?.success) {
        setPosts(r.data.data.posts || []);
        if (!tag) setTags(r.data.data.tags || []);
      }
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => { load(''); }, []);
  useEffect(() => {
    if (initialSlug) {
      axios.get(`${API}/public/blog/${initialSlug}`).then(r => {
        if (r.data?.success) setActivePost(r.data.data);
      }).catch(() => { /* silent */ });
    }
  }, [initialSlug]);

  const openPost = async (slug) => {
    try {
      const r = await axios.get(`${API}/public/blog/${slug}`);
      if (r.data?.success) {
        setActivePost(r.data.data);
        window.history.pushState({}, '', `/blog/${slug}`);
      }
    } catch { /* silent */ }
  };

  if (activePost) {
    return (
      <div className="min-h-screen bg-white text-zinc-900" data-testid="blog-post-page">
        <div className="max-w-3xl mx-auto px-6 py-10">
          <button onClick={() => { setActivePost(null); window.history.pushState({}, '', '/blog'); }}
            className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-800 mb-6" data-testid="blog-back-btn">
            <ArrowLeft size={16} /> Back to all posts
          </button>
          {activePost.cover_image && (
            <img src={activePost.cover_image} alt="" className="w-full aspect-video object-cover rounded-lg mb-6" />
          )}
          <div className="flex items-center gap-3 text-xs text-zinc-500 mb-3">
            <span className="flex items-center gap-1"><Calendar size={12} /> {(activePost.published_at || '').slice(0, 10)}</span>
            <span>·</span>
            <span>{activePost.author}</span>
            {activePost.tags?.length > 0 && (
              <>
                <span>·</span>
                {activePost.tags.map(t => (
                  <span key={t} className="px-2 py-0.5 bg-zinc-100 rounded-sm">{t}</span>
                ))}
              </>
            )}
          </div>
          <h1 className="text-4xl font-bold text-zinc-950 mb-4" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>{activePost.title}</h1>
          <p className="text-lg text-zinc-600 mb-8 leading-relaxed">{activePost.excerpt}</p>
          <div className="prose max-w-none text-zinc-700 leading-relaxed"
               style={{ fontSize: 15 }}
               dangerouslySetInnerHTML={{ __html: renderMd(activePost.body_md || '') }} />
          <div className="mt-12 pt-8 border-t border-zinc-200 text-sm text-zinc-500">
            Want to see FLOWRA in action for your business?{' '}
            <button onClick={() => onNavigate('signup')} className="text-[#0052FF] font-semibold underline">Start your free 14-day trial →</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white text-zinc-900" data-testid="blog-list-page">
      <div className="max-w-6xl mx-auto px-6 py-10">
        <button onClick={() => onNavigate('landing')} className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-800 mb-6">
          <ArrowLeft size={16} /> Home
        </button>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#0052FF] mb-3">FLOWRA Journal</p>
        <h1 className="text-4xl sm:text-5xl font-bold text-zinc-950 tracking-tight mb-3" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>Product updates &amp; SMB playbooks</h1>
        <p className="text-zinc-600 text-lg mb-10 max-w-2xl">Actionable notes from the FLOWRA team on Tally/Busy analytics, demand forecasting, and running a lean Indian business.</p>

        {tags.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mb-8">
            <Tag size={14} className="text-zinc-400" />
            <button onClick={() => { setActiveTag(''); load(''); }}
              className={`text-xs px-3 py-1 rounded-sm border ${activeTag === '' ? 'bg-zinc-950 text-white border-zinc-950' : 'bg-white border-zinc-200 text-zinc-600 hover:border-zinc-400'}`}>
              All
            </button>
            {tags.map(t => (
              <button key={t} onClick={() => { setActiveTag(t); load(t); }}
                className={`text-xs px-3 py-1 rounded-sm border ${activeTag === t ? 'bg-zinc-950 text-white border-zinc-950' : 'bg-white border-zinc-200 text-zinc-600 hover:border-zinc-400'}`}
                data-testid={`blog-tag-${t}`}>
                {t}
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <p className="text-zinc-400">Loading…</p>
        ) : posts.length === 0 ? (
          <p className="text-zinc-500 py-16 text-center">No posts yet. Check back soon!</p>
        ) : (
          <div className="grid md:grid-cols-2 gap-6">
            {posts.map(p => (
              <button key={p.post_id} onClick={() => openPost(p.slug)}
                className="text-left border border-zinc-200 rounded-lg overflow-hidden hover:border-zinc-400 transition-colors bg-white"
                data-testid={`blog-card-${p.slug}`}>
                {p.cover_image && <img src={p.cover_image} alt="" className="w-full aspect-video object-cover" />}
                <div className="p-5">
                  <div className="flex items-center gap-2 text-xs text-zinc-500 mb-2">
                    <span>{(p.published_at || '').slice(0, 10)}</span>
                    <span>·</span>
                    <span>{p.author}</span>
                  </div>
                  <h2 className="text-lg font-bold text-zinc-950 mb-2">{p.title}</h2>
                  <p className="text-sm text-zinc-600 line-clamp-2">{p.excerpt}</p>
                  <div className="flex items-center gap-1 mt-3 text-xs text-[#0052FF] font-semibold">
                    Read post <ChevronRight size={12} />
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default BlogListPage;
