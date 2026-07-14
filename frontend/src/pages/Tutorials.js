import React, { useMemo, useRef, useState } from 'react';
import { Play, Pause, GraduationCap, CheckCircle2, Circle, Clock, ChevronRight, Youtube, Volume2 } from 'lucide-react';

/**
 * FLOWRA Academy — in-app tutorial hub.
 * Phase 1 (iter-123): voice-sample chooser + full 30-lesson roadmap.
 * Phase 2: each lesson row will link to its finished YouTube video +
 * cheat-sheet PDF once mass-production is done.
 */

const VOICE_SAMPLES = [
  { id: 'coral',   label: 'Coral',   desc: 'Warm, friendly — best for Owner track & explainers' },
  { id: 'nova',    label: 'Nova',    desc: 'Energetic, upbeat — best for Salesman track' },
  { id: 'shimmer', label: 'Shimmer', desc: 'Bright, cheerful — best for Getting-Started' },
];

// 30-lesson roadmap. `status` = 'live' | 'in_progress' | 'planned'.
const TRACKS = [
  {
    key: 'getting-started',
    title: 'Getting Started',
    persona: 'Everyone',
    color: 'bg-blue-100 text-blue-700',
    lessons: [
      { n: 1, title: 'FLOWRA kya hai? (2 min mein)',        len: '90s',  status: 'in_progress' },
      { n: 2, title: 'Pehli baar login kaise karein',        len: '75s',  status: 'planned' },
      { n: 3, title: 'Home dashboard ka tour',               len: '2m',   status: 'planned' },
      { n: 4, title: 'FY aur Company choose karna',          len: '45s',  status: 'planned' },
    ],
  },
  {
    key: 'owner',
    title: 'Owner — "Run the business from your phone"',
    persona: 'Business Owner',
    color: 'bg-purple-100 text-purple-700',
    lessons: [
      { n: 5, title: 'KPI cards padhna — Sales, Orders, Outstanding, Beat',  len: '2m',  status: 'planned' },
      { n: 6, title: '"What\'s New" module — updates kahaan miltay hain',     len: '60s', status: 'planned' },
      { n: 7, title: 'Resource PDFs download karna',                          len: '90s', status: 'planned' },
      { n: 8, title: 'Financial pitch deck aur projections',                  len: '2m',  status: 'planned' },
      { n: 9, title: 'Super-admin: users, branches, license',                 len: '3m',  status: 'planned' },
    ],
  },
  {
    key: 'ops',
    title: 'Ops Manager — "Daily operations"',
    persona: 'User-admin',
    color: 'bg-emerald-100 text-emerald-700',
    lessons: [
      { n: 10, title: 'Sales tab — filters, drill-down, export',              len: '3m',  status: 'planned' },
      { n: 11, title: 'Inventory tab — ABC/D, stock groups, reorder alerts',  len: '3m',  status: 'planned' },
      { n: 12, title: 'CRM — Outstanding aur aging buckets',                  len: '2m',  status: 'planned' },
      { n: 13, title: 'CRM — Targets aur bulk %',                             len: '2m',  status: 'planned' },
      { n: 14, title: 'CRM — Payment Behaviour (score & delay)',              len: '90s', status: 'planned' },
      { n: 15, title: 'CA Corner overview',                                   len: '2m',  status: 'planned' },
      { n: 16, title: 'Backups aur restore ka workflow',                      len: '2m',  status: 'planned' },
      { n: 17, title: 'Dispatch mirror view',                                 len: '90s', status: 'planned' },
    ],
  },
  {
    key: 'salesman',
    title: 'Salesman — "On-the-road toolkit"',
    persona: 'Salesman',
    color: 'bg-amber-100 text-amber-700',
    lessons: [
      { n: 18, title: 'Salesman mobile dashboard',                            len: '90s', status: 'planned' },
      { n: 19, title: 'Visit / order record karna phone se',                  len: '2m',  status: 'planned' },
      { n: 20, title: 'Recommendation Engine ke tips',                        len: '90s', status: 'planned' },
      { n: 21, title: 'Personal target progress',                             len: '60s', status: 'planned' },
    ],
  },
  {
    key: 'ca',
    title: 'CA / Accountant — "Books & compliance"',
    persona: 'Accountant',
    color: 'bg-rose-100 text-rose-700',
    lessons: [
      { n: 22, title: 'Ledger PDF export (per customer)',                     len: '90s', status: 'planned' },
      { n: 23, title: 'Reconciliation window — date scope',                   len: '2m',  status: 'planned' },
      { n: 24, title: 'Tally/Busy sync status & retry',                       len: '2m',  status: 'planned' },
      { n: 25, title: 'GST-ready reports (jab module live ho)',               len: '2m',  status: 'planned' },
    ],
  },
  {
    key: 'agent',
    title: 'Desktop Sync Agent — advanced',
    persona: 'Anyone syncing Tally/Busy',
    color: 'bg-slate-100 text-slate-700',
    lessons: [
      { n: 26, title: 'Tally agent install on Windows',                       len: '2m',  status: 'planned' },
      { n: 27, title: 'First-time company mapping',                           len: '90s', status: 'planned' },
      { n: 28, title: '"Sync Health" kya batati hai',                         len: '90s', status: 'planned' },
      { n: 29, title: 'Top-5 red states — troubleshoot',                      len: '3m',  status: 'planned' },
      { n: 30, title: 'Busy Agent primer',                                    len: '2m',  status: 'planned' },
    ],
  },
];

const StatusBadge = ({ status }) => {
  if (status === 'live') {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700"><CheckCircle2 size={10} /> LIVE</span>;
  }
  if (status === 'in_progress') {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-700"><Clock size={10} /> IN PROGRESS</span>;
  }
  return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-500"><Circle size={10} /> Planned</span>;
};

const VoiceSampleCard = ({ sample, playing, onPlay }) => (
  <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-col gap-3 hover:border-blue-300 transition-colors" data-testid={`voice-card-${sample.id}`}>
    <div className="flex items-center justify-between">
      <div>
        <h4 className="text-base font-semibold text-slate-900 capitalize">{sample.label}</h4>
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
      id={`audio-${sample.id}`}
      src={`/tutorials/voice-samples/${sample.id}.mp3`}
      preload="metadata"
      data-testid={`voice-audio-${sample.id}`}
    />
  </div>
);

const Tutorials = () => {
  const [playing, setPlaying] = useState(null);
  const audioRefs = useRef({});

  const totalLessons = useMemo(() => TRACKS.reduce((n, t) => n + t.lessons.length, 0), []);
  const liveCount = useMemo(() => TRACKS.reduce((n, t) => n + t.lessons.filter(l => l.status === 'live').length, 0), []);

  const handlePlay = (id) => {
    // Stop any currently-playing audio first
    Object.values(audioRefs.current).forEach(a => { if (a && !a.paused) a.pause(); });
    const el = document.getElementById(`audio-${id}`);
    audioRefs.current[id] = el;
    if (!el) return;
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

  return (
    <div className="max-w-6xl mx-auto space-y-8" data-testid="tutorials-page">
      {/* Hero */}
      <div className="bg-gradient-to-br from-[#0F1B4C] to-[#2563EB] rounded-2xl p-8 text-white">
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center">
            <GraduationCap size={28} />
          </div>
          <div className="flex-1">
            <h1 className="text-3xl font-bold mb-1">FLOWRA Academy</h1>
            <p className="text-blue-100 text-sm max-w-2xl">
              Hinglish videos jo sirf 90 seconds mein ek concept samjhaate hain.
              Owner, salesman, ya accountant — sabke liye alag track.
              <span className="block mt-1 text-xs text-blue-200">Progress: {liveCount} of {totalLessons} lessons live · production in progress</span>
            </p>
          </div>
        </div>
      </div>

      {/* Voice sample chooser */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6">
        <div className="flex items-start gap-3 mb-4">
          <Volume2 size={22} className="text-[#2563EB] mt-0.5" />
          <div>
            <h2 className="text-lg font-bold text-slate-900">Pick the voiceover — female voices only</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Same Hinglish line, three different Indian-English female voices. Play each, reply to us with your pick — we'll lock it for all 30 lessons.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {VOICE_SAMPLES.map(s => (
            <VoiceSampleCard key={s.id} sample={s} playing={playing} onPlay={handlePlay} />
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
              {track.lessons.map(lesson => (
                <li key={lesson.n} className="px-5 py-3 flex items-center gap-4 hover:bg-slate-50 transition-colors" data-testid={`lesson-${lesson.n}`}>
                  <span className="w-8 h-8 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center text-xs font-semibold">{lesson.n}</span>
                  <span className="flex-1 text-sm text-slate-800">{lesson.title}</span>
                  <span className="text-xs text-slate-400 tabular-nums">{lesson.len}</span>
                  <StatusBadge status={lesson.status} />
                  {lesson.status === 'live' && (
                    <a className="text-blue-600 hover:text-blue-700" aria-label="Open on YouTube"><Youtube size={16} /></a>
                  )}
                  <ChevronRight size={14} className="text-slate-300" />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <p className="text-center text-xs text-slate-400 py-4">
        Videos will be uploaded to your FLOWRA YouTube channel. Each row will link directly once live.
      </p>
    </div>
  );
};

export default Tutorials;
