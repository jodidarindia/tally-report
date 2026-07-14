"""FLOWRA Academy — canonical 30-lesson manifest.

Each entry: (lesson_number, slug, title, voiceover_hinglish, length_hint).

The voiceover text is the *exact* string sent to OpenAI tts-1-hd.
Kept tight (100–180 words) so each lesson stays ≤ 2 min at natural pace.

Consumed by:
  • generate_all_voiceovers.py  → produces MP3 per lesson
  • render_all_lessons.py       → produces MP4 per lesson (with screencast)
  • build_youtube_metadata.py   → title/desc/tags per lesson
"""

# Voice locked (iter-125)
VOICE = "onyx"
MODEL = "tts-1-hd"

# ── 30 lessons — Hinglish scripts, business-owner tone ────────────
LESSONS = [
    # ── Getting Started (1–4) ────────────────────────────────────
    (1, "flowra-kya-hai", "FLOWRA kya hai? (2 min mein)",
     "Namaste! Main FLOWRA hoon — aapke business ka digital brain. "
     "Aap Tally ya Busy chalate hain? Toh aap jaante hain — data toh sab computer mein hai, "
     "lekin dekhne ke liye office jaana padta hai. Mobile se sales dekhni ho, outstanding check karna ho, "
     "ya salesman ka target dekhna ho — sab kuch phone pe milna chaahiye. Sahi baat? "
     "Bas yehi kaam FLOWRA karta hai. Ek chhoti si desktop app aapka Tally ya Busy ka data har roz "
     "cloud pe le jaati hai, automatic. Aur aap kahin se bhi — ghar, dukaan, ya safar mein — apne mobile "
     "ya laptop pe pura business dekh sakte hain. Sales report, customer wise outstanding, inventory aur "
     "ABC categorisation, salesman ke targets, CA corner mein reconciliation — sab kuch ek jagah. "
     "Aage ke videos mein hum ek-ek karke sab feature dekhenge, bilkul aasan bhaasha mein. Chaliye shuru karte hain!",
     "90s"),

    (2, "pehli-baar-login", "Pehli baar login kaise karein",
     "Chaliye pehli baar FLOWRA mein login karte hain. Sabse pehle browser mein flowralive.in kholiye. "
     "Upar right corner mein aapko Login button dikhega — usko click kijiye. "
     "Ab do cheezein daalni hain — aapka username aur password. Yeh dono aapko onboarding ke time diye gaye the — "
     "email pe ya WhatsApp pe. Nahi mile toh apne FLOWRA representative se poochh lijiye. "
     "Password daalne ke baad Sign In dabaaiye. Bas! Aap seedha apne Dashboard pe pahunch jaayenge. "
     "Ek zaroori baat — agar aap pehli baar login kar rahe hain, toh system aapko ek chhota sa tour dikhaayega. "
     "Uspe dhyaan dijiye — 30 second mein sab kuch samajh aa jaayega. "
     "Agla video mein hum Dashboard ka pura tour karenge.",
     "75s"),

    (3, "dashboard-tour", "Home dashboard ka tour",
     "Ye hai aapka FLOWRA Dashboard — aapke business ka homepage. Sabse upar aapko chaar cards dikhenge: "
     "Total Sales, Total Orders, Outstanding Amount, aur Beat Coverage. Yeh charon numbers har 30 second mein "
     "automatic refresh hote hain — Tally ka latest data. Aap manually bhi Refresh button daba sakte hain. "
     "Neeche What's New panel hai — jab bhi FLOWRA mein koi naya feature aata hai, yaha update dikhega. "
     "Aur bhi neeche aapko upcoming reminders, overdue customer digest, aur sync status dikhega. "
     "Upar navigation bar mein — Sales, CRM, Inventory, Analytics, Salesman, AI Reports, CA Corner — "
     "har tab ek alag feature ke liye hai. Right side mein FY selector hai — usko change karke aap kisi bhi "
     "financial year ka data dekh sakte hain. Simple, na?",
     "2m"),

    (4, "fy-company-choose", "FY aur Company choose karna",
     "FLOWRA multi-company support karta hai — matlab agar aapke paas ek se zyada Tally companies hain, "
     "toh aap dashboard ke upar company selector se switch kar sakte hain. Naam pe click kariye — "
     "list khulegi — jo company dekhni hai us pe click kariye. Data automatic uss company ka aa jaayega. "
     "Waisi hi tarah FY selector — abhi FY 2026-27 selected hai. Aap 2025-26 ya kisi bhi previous year ka data dekh "
     "sakte hain. Ek tip — agar aap sales ya outstanding ka trend dekhna chahte hain toh alag alag FY switch "
     "karke compare kariye. Chalo agle video mein Owner track shuru karte hain — KPI cards padhna seekhenge.",
     "45s"),

    # ── Owner Track (5–9) ────────────────────────────────────────
    (5, "owner-kpi-cards", "KPI cards padhna — Sales, Orders, Outstanding, Beat",
     "Owner ke liye pehla lesson — Dashboard ke chaar KPI cards ka matlab. Pehla card, Total Sales — is FY mein "
     "aapki poori sales value. Neeche chhote akshar mein compare hai — pichhle FY se kitna zyada ya kam. "
     "Doosra card, Total Orders — kitne unique sales vouchers banaye gaye. Teesra card, Outstanding Amount — "
     "customers ne kitna paisa dena hai. Yeh number jitna kam ho, utna hi business healthy. "
     "Chautha card, Beat Coverage — kitne percent customers ko is week visit kiya gaya. "
     "Agar Beat Coverage 60 percent se kam hai, toh sales team ko push kariye. In chaar numbers ko har subah "
     "phone pe dekh lijiye — 30 second mein pata chal jaayega ki business kaisa chal raha hai.",
     "2m"),

    (6, "owner-whats-new", "What's New module — updates kahaan miltay hain",
     "FLOWRA har mahine naye features release karta hai — bug fixes, improvements, aur naye tools. "
     "Jab bhi kuch naya aata hai, aapko Dashboard ke What's New panel mein dikhega — right side mein neeche. "
     "Har entry ke saath ek tag hota hai — NEW purple mein, FIX red mein, IMPROVE blue mein. "
     "Date bhi dikhti hai, taaki aap dekh saken kab release hua. "
     "Aap chahen toh yehi content ek PDF mein bhi download kar sakte hain — Resources section se, FLOWRA Whats New PDF. "
     "Yehi PDF aap apni team ke saath share bhi kar sakte hain WhatsApp pe. Simple aur updated — hamesha.",
     "60s"),

    (7, "owner-resource-pdfs", "Resource PDFs download karna",
     "FLOWRA aapko chaar zaroori PDFs deta hai — Landing Page ke Resources section mein. "
     "Pehla, Presentation — jo FLOWRA ka features overview hai, board meetings ke liye. "
     "Doosra, Deployment Guide — technical team ke liye ki setup kaise karein. "
     "Teesra, Training Booklet — aapke staff aur salesman ke liye step-by-step guide. "
     "Chautha, Customer Questionnaire — jab bhi naya customer onboard karna ho, yeh form use kariye. "
     "Aur haan — What's New PDF alag se, jo product updates ka summary hai. "
     "Sabhi PDFs FLOWRA branded hain, print-ready hain, aur WhatsApp par easily share ho jaati hain.",
     "90s"),

    (8, "owner-pitch-deck", "Financial pitch deck aur projections",
     "Owner ke liye ek special tool hai — Financial Pitch Deck. Yeh aapke business ki 3-year projection banata hai, "
     "aapke actual Tally data se. Investors ke saath meeting ho, ya bank loan ke liye documentation chaahiye — "
     "yeh deck ready hai. 16 pages, revenue growth chart, gross margin trend, cash flow projection. "
     "Ek teaser version bhi hai — 10 pages — WhatsApp par forward karne ke liye. "
     "Aur Excel projections file bhi, jismein har month ki numbers editable hain. "
     "Sabhi files apne aap generate hoti hain — Owner Console mein Generate Pitch Deck button dabaayein. "
     "Do minute mein PDF aur Excel dono ready.",
     "2m"),

    (9, "owner-superadmin", "Super-admin — users, branches, license",
     "Owner ke liye sabse powerful section — Super Admin. Yaha se aap teen kaam kar sakte hain. "
     "Ek — naye users add karna, unko role dena, aur access control set karna. Admin, User-admin, Salesman, ya CA. "
     "Do — branches manage karna. Har branch ko include ya exclude karna reports se. "
     "Teen — license window aur billing details. Agar company grow kar rahi hai aur zyada users chaahiye, "
     "yaha se upgrade request kar sakte hain. "
     "Ek zaroori tip — user delete mat kariye, disable kariye. Delete karne se unke past actions ka log gum ho sakta hai. "
     "Disable safe hai — audit trail bacha rehta hai.",
     "3m"),

    # ── Ops Manager Track (10–17) ────────────────────────────────
    (10, "ops-sales-tab", "Sales tab — filters, drill-down, export",
     "Ops manager ka pehla tool — Sales tab. Yaha aap har sales voucher dekh sakte hain. "
     "Upar filters hain — date range, salesman, customer, category. Filter lagate hi list update ho jaati hai. "
     "Kisi bhi voucher pe click kariye — details khul jaayenge. Items, quantities, rates, total. "
     "Do buttons upar hain — PDF aur Excel export. Dono files aapki company name ke header ke saath download hoti hain, "
     "professional look ke liye. Ek pro tip — Salesman filter lagakar Excel export kariye, aur monthly performance review "
     "ke liye salesman ko share kariye. Bahut asaan.",
     "3m"),

    (11, "ops-inventory-abc", "Inventory tab — ABC/D, stock groups, reorder",
     "Inventory tab mein aapko poora stock dikhta hai — item name, quantity, ABC category, stock group. "
     "ABC categorisation kya hai? A category — top 20 percent items jo 80 percent revenue laate hain. Focus items. "
     "B category — middle. C category — bottom. D category — dead stock, jo bahut kam bik raha hai. "
     "Stock groups Tally se aate hain — Engine Oil, Gear Oil, Transmission — apne group ke hisab se filter kariye. "
     "Reorder alerts bhi yaha dikhte hain — jab bhi kisi item ka stock reorder level se neeche jaata hai, "
     "red highlight ho jaata hai. Export bhi kar sakte hain PDF ya Excel mein — company name banner ke saath.",
     "3m"),

    (12, "ops-crm-outstanding", "CRM — Outstanding aur aging buckets",
     "CRM tab ka pehla section — Outstanding. Yaha aapke sabhi customers ki current outstanding dikhti hai. "
     "Har row mein customer name, ledger group, opening balance, total sales, paid amount, aur outstanding. "
     "Right side mein aging buckets — 0 to 30 din, 30 to 60, 60 to 90, aur 90 plus. "
     "Yeh sabse important number hai — 90 plus days ki outstanding matlab payment collection problem. "
     "Upar dropdown hai — All Customers ya ek specific ledger group ya state select kariye. "
     "Excel export bhi hai — poori list ek click mein. Salesman ko share kariye — payment collection ka focus milega.",
     "2m"),

    (13, "ops-crm-targets", "CRM — Targets aur bulk %",
     "CRM ka doosra section — Targets. Har customer ke liye ek annual target set kar sakte hain. "
     "Manually customer wise ya bulk mein — Bulk % Target button dabaakar. Pichhle FY ki sales ke upar "
     "10 percent, 20 percent, ya jo bhi percentage — sab customers ke liye ek saath set ho jaayega. "
     "Har row mein pichhle FY sales, target, current FY achievement, aur percentage. "
     "Neeche monthly split bhi hai — April se March tak, har month ki sales. "
     "Excel export kariye — poora target report ready. Sales meeting mein use kariye — kaun peeche hai, kise push karna hai — clear.",
     "2m"),

    (14, "ops-crm-payment-behavior", "CRM — Payment Behaviour",
     "CRM ka teesra section — Payment Behaviour. Har customer ka payment pattern analyse hota hai. "
     "Pay Ratio dikhta hai — kitna sales value pay ho gaya. 80 percent se upar green, 50 se 80 yellow, "
     "50 se neeche red. Avg Delay bhi hai — average kitne din late paise aate hain. "
     "Score column ek combined rating hai — 0 se 100 tak. High score matlab reliable customer, credit badhaao. "
     "Low score matlab careful raho, advance payment maango. "
     "Yeh data business decisions mein bahut useful hai — kis customer ko credit dena hai, kise nahi.",
     "90s"),

    (15, "ops-ca-corner", "CA Corner overview",
     "CA Corner — accountant ke liye special section. Yaha se aap sync status, reconciliation, "
     "aur ledger PDF export kar sakte hain. Har customer ka detailed ledger — opening balance, "
     "har transaction, closing balance — professional PDF format mein. GST-ready format bhi upcoming hai. "
     "CA Corner mein aap window bhi set kar sakte hain — reconcile ke liye start date aur end date. "
     "Sync history mein dekh sakte hain — kab kya sync hua, koi error toh nahi. Yeh section mainly CA aur "
     "accounts team use karti hai.",
     "2m"),

    (16, "ops-backups", "Backups aur restore workflow",
     "Data safety FLOWRA mein highest priority hai. Har raat 2 baje automatic backup hota hai — cloud pe. "
     "Owner Console mein Backups section mein aap dekh sakte hain — last 30 days ke backups list. "
     "Har backup ka size, timestamp, aur restore button. "
     "Kabhi galti se koi wrong change hua, ya data corrupt lag raha hai — bas ek click mein pichhle backup se restore kar sakte hain. "
     "Ek zaroori baat — restore karne se pehle current state ka backup lena chaahiye. Manual Backup button hai — dabaayein, "
     "current snapshot save ho jaayega. Fir safe se restore kariye.",
     "2m"),

    (17, "ops-dispatch-mirror", "Dispatch mirror view",
     "Dispatch mirror ek unique feature hai. Aapke godown ya factory mein jo dispatch hota hai — trucks, LR numbers, "
     "consignee — sab kuch mobile pe live dikhta hai. "
     "Sales tab mein Dispatch column enable kariye — har voucher ke saath dispatch through, destination, aur LR details. "
     "Filter bhi kar sakte hain — kis truck se, kis city ko, kya bheja. "
     "Owner ke liye bahut useful — office nahi jaana padta, dispatch status phone pe milta hai. "
     "Aur Google Drive integration ke saath — bilty aur invoice PDFs bhi automatically link ho jaate hain.",
     "90s"),

    # ── Salesman Track (18–21) ──────────────────────────────────
    (18, "salesman-mobile", "Salesman mobile dashboard",
     "Salesman ke liye ek alag simplified dashboard hai. Login karte hi aapko sirf apne customers, "
     "apne target, aur apne beat dikhte hain. My Sales — is month kitna kiya. "
     "My Target — kitna reach karna hai. My Customers — poori list, filter aur search ke saath. "
     "My Beat — is week kis kis ko visit karna hai. "
     "Owner ka poora data nahi dikhta — sirf aapka apna. Clean, focused, aur phone pe fast. "
     "Field mein use karne ke liye perfect.",
     "90s"),

    (19, "salesman-visit-order", "Visit / order record karna phone se",
     "Salesman phone se hi visit aur order record kar sakta hai. Ek customer pe pahunche, "
     "app kholiye, customer select kariye, Record Visit dabaaein. Location automatic capture ho jaati hai. "
     "Agar order milta hai — Create Order dabaaiye. Items add kariye, quantity daaliye, submit. "
     "Yeh order Tally mein bhi automatically sync ho jaayega raat ko. "
     "Digital record milta hai — kab kaun kahaan gaya, kya bik gaya. Owner ke liye transparency, "
     "salesman ke liye productivity. Sabka fayda.",
     "2m"),

    (20, "salesman-recommendations", "Recommendation Engine ke tips",
     "FLOWRA aapko AI-powered recommendations bhi deta hai. Salesman dashboard mein Recommendations panel dekhiye. "
     "System aapke customers ka past order pattern analyse karta hai aur suggest karta hai — "
     "kis customer ko is week visit karna chaahiye, kaunse products offer karna hai. "
     "Missed customer — jo 30 din se order nahi diya, follow up kariye. "
     "Cross-sell opportunity — is customer ne Engine Oil liya hai, Gear Oil bhi offer kariye. "
     "Yeh tips subah ke coffee ke saath 2 minute mein padh lo — day plan ready.",
     "90s"),

    (21, "salesman-target", "Personal target progress",
     "Har salesman ke liye personal target dashboard hai. Ek circular progress bar dikhta hai — "
     "current achievement percentage. Green matlab on-track, yellow slightly behind, red matlab critical push chaahiye. "
     "Neeche month-wise breakdown — April se abhi tak har month kitna kiya. "
     "Bhi dikhta hai — remaining amount, aur remaining days. Simple math — daily kitna achieve karna hai. "
     "Yeh ek motivation tool hai — daily open kariye, apne progress ko dekhiye. Chhote goals set kariye, "
     "monthly target automatic ban jaayega.",
     "60s"),

    # ── CA / Accountant Track (22–25) ───────────────────────────
    (22, "ca-ledger-pdf", "Ledger PDF export (per customer)",
     "CA aur accountant ke liye pehla useful tool — customer ledger PDF export. "
     "CRM tab mein kisi bhi customer pe click kariye. Ledger button dabaaein. "
     "System ek professional PDF banata hai — company name header, customer details, poora ledger, "
     "opening balance se closing balance tak har transaction. GST ready format mein. "
     "Sabse achi baat — client ko bhejne ke liye ekdum ready. Print pe bhi accha lagta hai. "
     "Ek click mein poora customer ka statement.",
     "90s"),

    (23, "ca-reconciliation", "Reconciliation window — date scope",
     "Reconciliation FLOWRA mein powerful feature hai. Kabhi Tally aur FLOWRA ke numbers thoda match nahi karte — "
     "toh Reconcile button hai, jo do numbers ko align karta hai. "
     "Window bhi set kar sakte hain — start date aur end date. Sirf uss period ke transactions reconcile honge. "
     "Deletion bhi scoped hai — matlab agar window mein koi voucher extra hai, sirf woh delete hoga, "
     "poora data corrupt nahi hoga. Safe aur precise. "
     "Yeh feature CA aur audit team ke liye life-saver hai — quarterly reconciliation ekdum easy.",
     "2m"),

    (24, "ca-sync-status", "Tally/Busy sync status & retry",
     "Sync History tab mein aapko har sync ka record milta hai. Timestamp, kitne vouchers aaye, "
     "kaunsi tables update hui, koi error toh nahi. Green tick matlab successful, red exclamation matlab failed. "
     "Failed sync pe click kariye — error detail milega. Common issues — Tally band tha, network gaya, "
     "ya password galat tha. Retry button hai — dabaaein, agent turant fir se try karega. "
     "Agar bar bar fail ho raha hai, WhatsApp par FLOWRA support ko screenshot bhejo — team turant help karegi.",
     "2m"),

    (25, "ca-gst-reports", "GST-ready reports (jab module live ho)",
     "Aane wale weeks mein GST module launch hoga. Aap GSTR JSON portal se download karke FLOWRA CA Corner mein "
     "upload kar paayenge. System automatically reconcile karega — aapke Tally sales aur portal ke figures. "
     "Mismatched invoices highlight honge — kaunsa invoice portal mein hai lekin Tally mein nahi, ya vice versa. "
     "Monthly GSTR filing tension free ho jaayegi. "
     "Jab yeh feature live hoga, main is video ko update kar dunga — Academy ka big update aane wala hai.",
     "2m"),

    # ── Desktop Sync Agent (26–30) ──────────────────────────────
    (26, "agent-tally-install", "Tally agent install on Windows",
     "Tally agent Windows ke liye ek chhota sa desktop application hai. Downloads section se agent installer download kariye. "
     "Double click karke run kariye — Next, Next, Install. 30 second mein install ho jaayega. "
     "Icon system tray mein aa jaayega — right bottom corner mein. Right click karke Open kariye. "
     "Ek chhota window kholega — apna FLOWRA login credentials daaliye. Bas! "
     "Ab har raat 2 baje ye agent apne aap aapka Tally data cloud pe bhejega. Aapko kuch nahi karna — "
     "Tally chalu rakhen bas.",
     "2m"),

    (27, "agent-company-mapping", "First-time company mapping",
     "Pehli baar agent install hone ke baad, ek zaroori step hai — company mapping. "
     "Agent kholiye, Companies tab kholiye. Aapki Tally mein jitni companies hain, sab dikhengi. "
     "Har company ke saathi ek FLOWRA company assign karni hai. Dropdown se select kariye. "
     "Agar aap sirf ek company use karte hain, toh mapping easy hai. Multi-company setup mein carefully match kariye — "
     "wrong mapping se data mix ho sakta hai. "
     "Save Mapping dabaaein. Ho gaya — ab data uss company ke liye sync hoga.",
     "90s"),

    (28, "agent-sync-health", "Sync Health kya batati hai",
     "Agent ke Home tab mein ek indicator hai — Sync Health. Green matlab sab theek. "
     "Yellow matlab warning — jaise slow network ya large data queue. Red matlab problem — sync fail ho raha hai. "
     "Right side mein details bhi milte hain — last sync time, next scheduled sync, aur pending vouchers count. "
     "Agar Sync Health kuch din se yellow hai, ek baar manual Sync Now button dabaaein. Usually issue resolve ho jaata hai. "
     "Red state mein, next video dekhiye — troubleshooting steps.",
     "90s"),

    (29, "agent-troubleshoot", "Top-5 red states — troubleshoot",
     "Agent red state mein ho toh paanch common problems check kariye. "
     "Pehla — Tally band hai. Tally kholiye aur company load karo. "
     "Doosra — network issue. Internet check kariye. "
     "Teesra — ODBC not enabled. Tally F1 Configure mein ODBC enable karna zaroori hai. "
     "Chautha — password mismatch. Agar Tally password badla hai, agent mein bhi update kariye. "
     "Paanchwa — company path badal gaya. Agent settings mein new path daaliye. "
     "In paanch mein se koi ek fix karne se 90 percent problems solve ho jaate hain. "
     "Nahi ho, toh WhatsApp par FLOWRA support ko error screenshot bhejo — team help karegi.",
     "3m"),

    (30, "agent-busy-primer", "Busy Agent primer",
     "Busy ke liye bhi FLOWRA ka alag agent hai. Tally agent jaisa hi, bas ek difference — Busy ke .bds files "
     "ke saath kaam karta hai. Installation same — download, install, login. "
     "Company mapping bhi similar — Busy companies dikhengi, FLOWRA companies assign karo. "
     "Ek important note — Busy agent abhi licensed Busy 21 installations ke liye best hai. "
     "Demo version mein encryption password differ hota hai, so demo pe testing avoid kariye. "
     "Baaki sab features Tally agent jaisi hi hai — sync health, retry, company mapping. "
     "Agar aap Busy user hain, WhatsApp par contact kariye, hum aapko dedicated setup call denge.",
     "2m"),
]
