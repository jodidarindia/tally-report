import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { Play, Pause, GraduationCap, CheckCircle2, Circle, Clock, ChevronRight, Youtube, Volume2, Trophy } from 'lucide-react';

/**
 * FLOWRA Academy — in-app tutorial hub with per-user completion tracking.
 *
 * Iter-125:
 *   - Voice locked to Onyx (male, deep, authoritative).
 *   - All 30 voiceovers loaded from /tutorials/manifest.json.
 *   - Per-user completion tracked via /api/academy/progress. A lesson row
 *     shows a green tick the moment cumulative playback ≥ 60%.
 *   - Playback progress POSTed every 5 seconds while audio plays.
 */

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const VOICE_SAMPLES = [
  { id: 'echo', label: 'Echo', desc: 'Smooth, calm' },
  { id: 'onyx', label: 'Onyx', desc: 'Deep, authoritative — LOCKED for all 30 lessons' },
  { id: 'ash',  label: 'Ash',  desc: 'Clear, articulate' },
];

// Track / lesson metadata (30 lessons). The audio URL comes from the
// public manifest at /tutorials/manifest.json (auto-generated on backend).
const TRACKS = [
  {
    key: 'getting-started', title: 'Getting Started', persona: 'Everyone',
    color: 'bg-blue-100 text-blue-700',
    lessons: [
      { n: 1, title: 'FLOWRA kya hai? (2 min mein)',        len: '90s' },
      { n: 2, title: 'Pehli baar login kaise karein',        len: '75s' },
      { n: 3, title: 'Home dashboard ka tour',               len: '2m'  },
      { n: 4, title: 'FY aur Company choose karna',          len: '45s' },
    ],
  },
  {
    key: 'owner', title: 'Owner — "Run the business from your phone"',
    persona: 'Business Owner', color: 'bg-purple-100 text-purple-700',
    lessons: [
      { n: 5, title: 'KPI cards padhna — Sales, Orders, Outstanding, Beat', len: '2m'  },
      { n: 6, title: 'What\u2019s New module — updates kahaan miltay hain',   len: '60s' },
      { n: 7, title: 'Resource PDFs download karna',                         len: '90s' },
      { n: 8, title: 'Financial pitch deck aur projections',                 len: '2m'  },
      { n: 9, title: 'Super-admin — users, branches, license',               len: '3m'  },
    ],
  },
  {
    key: 'ops', title: 'Ops Manager — "Daily operations"',
    persona: 'User-admin', color: 'bg-emerald-100 text-emerald-700',
    lessons: [
      { n: 10, title: 'Sales tab — filters, drill-down, export',             len: '3m'  },
      { n: 11, title: 'Inventory tab — ABC/D, stock groups, reorder',        len: '3m'  },
      { n: 12, title: 'CRM — Outstanding aur aging buckets',                 len: '2m'  },
      { n: 13, title: 'CRM — Targets aur bulk %',                            len: '2m'  },
      { n: 14, title: 'CRM — Payment Behaviour',                             len: '90s' },
      { n: 15, title: 'CA Corner overview',                                  len: '2m'  },
      { n: 16, title: 'Backups aur restore workflow',                        len: '2m'  },
      { n: 17, title: 'Dispatch mirror view',                                len: '90s' },
    ],
  },
  {
    key: 'salesman', title: 'Salesman — "On-the-road toolkit"',
    persona: 'Salesman', color: 'bg-amber-100 text-amber-700',
    lessons: [
      { n: 18, title: 'Salesman mobile dashboard',           len: '90s' },
      { n: 19, title: 'Visit / order record karna phone se', len: '2m'  },
      { n: 20, title: 'Recommendation Engine ke tips',       len: '90s' },
      { n: 21, title: 'Personal target progress',            len: '60s' },
    ],
  },
  {
    key: 'ca', title: 'CA / Accountant — "Books & compliance"',
    persona: 'Accountant', color: 'bg-rose-100 text-rose-700',
    lessons: [
      { n: 22, title: 'Ledger PDF export (per customer)',    len: '90s' },
      { n: 23, title: 'Reconciliation window — date scope',  len: '2m'  },
      { n: 24, title: 'Tally/Busy sync status & retry',      len: '2m'  },
      { n: 25, title: 'GST-ready reports (upcoming)',        len: '2m'  },
    ],
  },
  {
    key: 'agent', title: 'Desktop Sync Agent — advanced',
    persona: 'Anyone syncing Tally/Busy', color: 'bg-slate-100 text-slate-700',
    lessons: [
      { n: 26, title: 'Tally agent install on Windows',       len: '2m'  },
      { n: 27, title: 'First-time company mapping',           len: '90s' },
      { n: 28, title: 'Sync Health kya batati hai',           len: '90s' },
      { n: 29, title: 'Top-5 red states — troubleshoot',      len: '3m'  },
      { n: 30, title: 'Busy Agent primer',                    len: '2m'  },
    ],
  },
];

const StatusBadge = ({ completed, hasAudio }) => {
  if (completed) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700" data-testid="badge-completed">
        <CheckCircle2 size={10} /> COMPLETED
      </span>
    );
  }
  if (hasAudio) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-700">
        <Volume2 size={10} /> AUDIO READY
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-500">
      <Circle size={10} /> Planned
    </span>
  );
};

const VoiceSampleCard = ({ sample, playing, onPlay, locked }) => (
  <div className={`bg-white border rounded-xl p-4 flex flex-col gap-3 transition-colors ${locked ? 'border-blue-500 ring-2 ring-blue-100' : 'border-slate-200 hover:border-blue-300'}`} data-testid={`voice-card-${sample.id}`}>
    <div className="flex items-center justify-between">
      <div>
        <div className="flex items-center gap-2">
          <h4 className="text-base font-semibold text-slate-900 capitalize">{sample.label}</h4>
          {locked && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-600 text-white">LOCKED</span>}
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{sample.desc}</p>
      </div>
      <button
        onClick={() => onPlay(sample.id)}
        className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${playing === sample.id ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-blue-100 hover:text-blue-700'}`}
        data-testid={`voice-play-${sample.id}`}
        aria-label={`Play ${sample.label} voice sample`}
      >
        {playing === sample.id ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
      </button>
    </div>
    <audio
      id={`audio-sample-${sample.id}`}
      src={`/tutorials/voice-samples/${sample.id}.mp3`}
      preload="metadata"
      data-testid={`voice-audio-${sample.id}`}
    />
  </div>
);

const Tutorials = () => {
  const [playing, setPlaying] = useState(null);          // sample voice id or `lesson:N`
  const [manifest, setManifest] = useState(null);
  const [progressMap, setProgressMap] = useState({});    // { [lesson_n]: {completed, progress_pct} }
  const audioRefs = useRef({});
  const heartbeat = useRef({});                          // { [lesson_n]: intervalId }

  const totalLessons = 30;
  const completedCount = useMemo(
    () => Object.values(progressMap).filter(p => p.completed).length,
    [progressMap]
  );

  // Load public audio manifest (which lessons have voiceover MP3)
  useEffect(() => {
    fetch('/tutorials/manifest.json', { cache: 'no-cache' })
      .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setManifest)
      .catch(() => setManifest({ voice: 'onyx', lessons: [] }));
  }, []);

  // Load per-user completion state
  useEffect(() => {
    axios.get(`${API}/academy/progress`)
      .then(({ data }) => {
        if (!data?.success) return;
        const map = {};
        (data.data?.lessons || []).forEach(l => { map[l.n] = l; });
        setProgressMap(map);
      })
      .catch(err => console.warn('Academy progress fetch failed', err));
  }, []);

  const audioUrlFor = (n) => {
    const entry = manifest?.lessons?.find(l => l.n === n);
    return entry?.audio_url || null;
  };
  const videoUrlFor = (n) => `/tutorials/lessons/lesson-${String(n).padStart(2, '0')}.mp4`;

  const [previewLesson, setPreviewLesson] = useState(null);   // {n, videoUrl}
  const previewVideoRef = useRef(null);

  const openPreview = (n) => {
    // Stop any audio first
    Object.values(audioRefs.current).forEach(a => { if (a && !a.paused) a.pause(); });
    Object.values(heartbeat.current).forEach(id => id && clearInterval(id));
    heartbeat.current = {};
    setPlaying(null);
    setPreviewLesson({ n, videoUrl: videoUrlFor(n) });
  };

  const closePreview = () => {
    if (previewVideoRef.current) previewVideoRef.current.pause();
    setPreviewLesson(null);
  };

  // Heartbeat progress for the modal video preview
  useEffect(() => {
    if (!previewLesson) return undefined;
    const el = previewVideoRef.current;
    if (!el) return undefined;
    const n = previewLesson.n;
    const send = () => {
      if (!el.duration || Number.isNaN(el.duration)) return;
      const pct = (el.currentTime / el.duration) * 100;
      postProgress(n, pct);
    };
    const id = setInterval(send, 5000);
    const onEnded = () => {
      clearInterval(id);
      postProgress(n, 100);
    };
    el.addEventListener('ended', onEnded);
    return () => {
      clearInterval(id);
      el.removeEventListener('ended', onEnded);
    };
  }, [previewLesson]);

  const postProgress = async (n, pct) => {
    try {
      const { data } = await axios.post(`${API}/academy/progress`, { lesson: n, progress_pct: pct });
      if (data?.success && data.data) {
        setProgressMap(prev => ({ ...prev, [n]: { ...prev[n], ...data.data } }));
      }
    } catch (e) { /* silent — UX shouldn't stall on network errors */ }
  };

  // Stop any playing sample OR lesson before starting another
  const stopAll = () => {
    Object.values(audioRefs.current).forEach(a => { if (a && !a.paused) a.pause(); });
    Object.values(heartbeat.current).forEach(id => id && clearInterval(id));
    heartbeat.current = {};
  };

  const handleSamplePlay = (id) => {
    stopAll();
    const el = document.getElementById(`audio-sample-${id}`);
    if (!el) return;
    audioRefs.current[`sample-${id}`] = el;
    if (playing === id) {
      el.pause();
      setPlaying(null);
    } else {
      el.currentTime = 0;
      el.play();
      setPlaying(id);
      el.onended = () => setPlaying(null);
    }
  };

  const handleLessonPlay = (n) => {
    stopAll();
    const key = `lesson:${n}`;
    const el = document.getElementById(`audio-lesson-${n}`);
    if (!el) return;
    audioRefs.current[key] = el;
    if (playing === key) {
      el.pause();
      setPlaying(null);
      return;
    }
    el.play();
    setPlaying(key);

    // Send progress every 5 sec + on ended / pause
    const send = () => {
      if (!el.duration || Number.isNaN(el.duration)) return;
      const pct = (el.currentTime / el.duration) * 100;
      postProgress(n, pct);
    };
    heartbeat.current[n] = setInterval(send, 5000);
    el.onended = () => {
      clearInterval(heartbeat.current[n]);
      delete heartbeat.current[n];
      postProgress(n, 100);
      setPlaying(null);
    };
    el.onpause = () => {
      // Flush progress on pause too
      if (heartbeat.current[n]) send();
    };
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8" data-testid="tutorials-page">
      {/* Hero with completion counter */}
      <div className="bg-gradient-to-br from-[#0F1B4C] to-[#2563EB] rounded-2xl p-8 text-white">
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center">
            <GraduationCap size={28} />
          </div>
          <div className="flex-1">
            <h1 className="text-3xl font-bold mb-1">FLOWRA Academy</h1>
            <p className="text-blue-100 text-sm max-w-2xl">
              Hinglish videos jo 60–180 seconds mein ek concept samjhaate hain.
              Owner, salesman, ya accountant — sabke liye alag track.
            </p>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-2 text-white/90 justify-end mb-1">
              <Trophy size={18} className="text-amber-300" />
              <span className="font-semibold text-lg" data-testid="completion-counter">
                {completedCount} / {totalLessons}
              </span>
            </div>
            <p className="text-[11px] text-blue-200">lessons completed</p>
            <div className="mt-2 h-1.5 w-32 rounded-full bg-white/10 overflow-hidden">
              <div className="h-full bg-emerald-400 transition-all" style={{ width: `${(completedCount / totalLessons) * 100}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Voice sample chooser (Onyx locked) */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6">
        <div className="flex items-start gap-3 mb-4">
          <Volume2 size={22} className="text-[#2563EB] mt-0.5" />
          <div>
            <h2 className="text-lg font-bold text-slate-900">Voice locked — Onyx</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              All 30 lessons rendered in the <b>Onyx</b> voice (deep, authoritative, business-appropriate).
              You can still preview the alternative voices below.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {VOICE_SAMPLES.map(s => (
            <VoiceSampleCard key={s.id} sample={s} playing={playing} onPlay={handleSamplePlay} locked={s.id === 'onyx'} />
          ))}
        </div>
      </div>

      {/* Track roadmap */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-slate-900">30-lesson roadmap</h2>
        {TRACKS.map(track => (
          <div key={track.key} className="bg-white border border-slate-200 rounded-2xl overflow-hidden" data-testid={`track-${track.key}`}>
            <div className="px-5 py-3 flex items-center justify-between border-b border-slate-100">
              <div className="flex items-center gap-3">
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${track.color}`}>{track.persona}</span>
                <h3 className="font-semibold text-slate-900">{track.title}</h3>
              </div>
              <span className="text-xs text-slate-400">{track.lessons.length} lessons</span>
            </div>
            <ul className="divide-y divide-slate-100">
              {track.lessons.map(lesson => {
                const audio = audioUrlFor(lesson.n);
                const prog = progressMap[lesson.n] || {};
                const isPlaying = playing === `lesson:${lesson.n}`;
                return (
                  <li key={lesson.n} className="px-5 py-3 flex items-center gap-4 hover:bg-slate-50 transition-colors" data-testid={`lesson-${lesson.n}`}>
                    <span className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold ${prog.completed ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                      {prog.completed ? <CheckCircle2 size={16} /> : lesson.n}
                    </span>
                    <span className="flex-1 text-sm text-slate-800">{lesson.title}</span>
                    <span className="text-xs text-slate-400 tabular-nums">{lesson.len}</span>
                    {typeof prog.progress_pct === 'number' && prog.progress_pct > 0 && !prog.completed && (
                      <span className="text-[11px] text-slate-500 tabular-nums" data-testid={`lesson-${lesson.n}-pct`}>
                        {Math.round(prog.progress_pct)}%
                      </span>
                    )}
                    <StatusBadge completed={prog.completed} hasAudio={!!audio} />
                    {audio && (
                      <>
                        <button
                          onClick={() => openPreview(lesson.n)}
                          className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                          data-testid={`lesson-${lesson.n}-watch-btn`}
                          aria-label={`Watch lesson ${lesson.n}`}
                        >
                          <Play size={12} /> Watch
                        </button>
                        <button
                          onClick={() => handleLessonPlay(lesson.n)}
                          className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors ${isPlaying ? 'bg-slate-700 text-white' : 'bg-slate-100 text-slate-700 hover:bg-blue-100 hover:text-blue-700'}`}
                          data-testid={`lesson-${lesson.n}-play-btn`}
                          aria-label={`Play audio for lesson ${lesson.n}`}
                          title="Audio only"
                        >
                          {isPlaying ? <Pause size={12} /> : <Volume2 size={12} />}
                        </button>
                        <audio id={`audio-lesson-${lesson.n}`} src={audio} preload="metadata" />
                      </>
                    )}
                    <ChevronRight size={14} className="text-slate-300" />
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      <p className="text-center text-xs text-slate-400 py-4">
        Audio + video ready for all 30 lessons. Videos coming to your FLOWRA YouTube channel — completed lessons will show <Youtube size={12} className="inline text-red-500" /> once uploaded.
      </p>

      {/* Video preview modal */}
      {previewLesson && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={closePreview}
          data-testid="video-preview-modal"
        >
          <div
            className="bg-slate-900 rounded-2xl overflow-hidden shadow-2xl max-w-5xl w-full"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 bg-slate-800">
              <div className="flex items-center gap-3 text-white">
                <GraduationCap size={20} className="text-blue-400" />
                <span className="font-semibold">Lesson {previewLesson.n}</span>
                <span className="text-xs text-slate-400">·  progress auto-saves at 60%</span>
              </div>
              <button
                onClick={closePreview}
                className="text-slate-400 hover:text-white text-2xl font-light leading-none"
                aria-label="Close preview"
                data-testid="video-preview-close"
              >
                ×
              </button>
            </div>
            <video
              ref={previewVideoRef}
              src={previewLesson.videoUrl}
              controls
              autoPlay
              className="w-full aspect-video bg-black"
              data-testid="video-preview-player"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default Tutorials;
