"""Improvement actions and habits, each graded for evidence and risk.

Evidence:  strong   = replicated studies / clinical trials
           moderate = some studies, consistent direction
           weak     = little or indirect evidence, mostly community reports
           none     = claims without support
Risk:      low / medium / high

Sources are listed in docs/habits-sources.md.
"""

# ---------------------------------------------------------------- by area
# Keyed by improvement area; the report pulls these in when an area is flagged.
AREA_ACTIONS = {
    "leanness": {
        "title": "Facial leanness (facial fat / bloat)",
        "changeable": "high",
        "why": "The strongest, most reliable predictor of ratings in the reference data. "
               "Fuller faces (wider cheeks relative to height, jaw rounded by fat) rate lower.",
        "actions": [
            ("Get to roughly 10-15% body fat (men) / 18-25% (women) with a moderate calorie "
             "deficit (~300-500 kcal/day) and high protein (1.6-2.2 g/kg)",
             "strong", "low", "8-20 weeks"),
            ("Lift weights 3x/week while dieting so the weight lost is fat, not muscle",
             "strong", "low", "ongoing"),
            ("Cut alcohol, especially in the days before photos or events: it causes facial puffiness "
             "and redness", "moderate", "low", "days"),
            ("Keep sodium steady and potassium high (vegetables, beans, potatoes): big salt spikes "
             "cause next-day water retention in the face", "weak", "low", "1-2 days"),
            ("Sleep 7-9 h; short sleep makes faces look puffier and less healthy", "moderate", "low", "days"),
        ],
    },
    "eyes": {
        "title": "Eye area (eye size vs spacing, brow position)",
        "changeable": "low",
        "why": "Larger-looking eyes relative to the gap between them, and brows set closer to the "
               "eyes ('hunter eyes'), go with higher ratings. Bone and soft tissue set most of this.",
        "actions": [
            ("Fix sleep and allergies first: dark circles and puffy lids make eyes look smaller",
             "moderate", "low", "weeks"),
            ("Keep brows full, especially the lower edge; only remove strays and the unibrow. "
             "Over-plucking raises the brow line visually", "weak", "low", "2-4 weeks"),
            ("Lower body fat: fat around the orbit and upper lid reduces visible eye area",
             "weak", "low", "months"),
            ("Pick glasses that do not shrink the eyes (strong minus lenses do; ask about high-index "
             "lenses, or consider contacts)", "moderate", "low", "immediate"),
            ("Clinical option for marked eyelid hooding or lower-lid issues: oculoplastic surgeon "
             "consultation, never DIY", "moderate", "medium", "-"),
        ],
    },
    "lower_third": {
        "title": "Chin and lower third",
        "changeable": "medium",
        "why": "A longer chin relative to the philtrum (lip-to-nose distance) goes with higher ratings. "
               "Community target ~2:1 chin-to-philtrum; the reference median is about 2.0.",
        "actions": [
            ("Men: grow heavy stubble or a short beard shaped longer at the chin and clean under the "
             "jawline; this visually lengthens and squares the chin", "moderate", "low", "2-6 weeks"),
            ("Keep a clean neckline (trim below the jaw) so the jaw-neck angle reads sharper",
             "weak", "low", "immediate"),
            ("Lose fat under the chin before judging your chin; submental fat hides projection",
             "moderate", "low", "months"),
            ("See an orthodontist if your bite is off; jaw position and lip support change with it",
             "moderate", "low", "1-3 years"),
            ("Clinical options for a genuinely recessed chin: genioplasty or chin implant "
             "(board-certified surgeon). Fillers are temporary.", "moderate", "medium", "-"),
        ],
    },
    "midface": {
        "title": "Midface proportions",
        "changeable": "low",
        "why": "A compact midface (shorter distance from eyes to mouth relative to eye spacing) "
               "goes with slightly higher ratings for men. This is skeletal.",
        "actions": [
            ("Moustache/stubble on the upper lip visually shortens a long philtrum", "weak", "low", "weeks"),
            ("Hairstyles with some volume on top and fuller sides balance a long midface",
             "weak", "low", "next haircut"),
            ("Skeletal changes need orthognathic surgery for a real functional problem "
             "(bite, airway), assessed by a maxillofacial surgeon", "strong", "high", "-"),
        ],
    },
    "symmetry": {
        "title": "Symmetry",
        "changeable": "low",
        "why": "More symmetric faces rate slightly higher. Most asymmetry is skeletal or dental; "
               "some is soft tissue and habit.",
        "actions": [
            ("Use a side part toward the fuller side of the face; asymmetric hair hides asymmetry "
             "better than a centre part", "weak", "low", "next haircut"),
            ("Chew on both sides; one-sided chewing can enlarge one masseter", "weak", "low", "months"),
            ("Sleep on your back if you can; face-down sleeping adds one-sided creases over years",
             "weak", "low", "years"),
            ("Find your better side for photos (take both and compare)", "moderate", "low", "immediate"),
            ("Dental check if your bite or smile is crooked", "moderate", "low", "-"),
        ],
    },
    "harmony": {
        "title": "Harmony (closeness to the average face)",
        "changeable": "low",
        "why": "Faces close to the population average rate higher. This is mostly bone structure; "
               "framing (hair, beard, glasses) changes how proportions read.",
        "actions": [
            ("Ask a good barber for a cut that balances your face shape (e.g. more height for round "
             "faces, fuller sides for long faces)", "weak", "low", "next haircut"),
            ("Use facial hair to correct proportions: chin length for a short lower third, "
             "fuller sides for a narrow face", "weak", "low", "weeks"),
            ("Glasses frames roughly as wide as the face and following the brow line",
             "weak", "low", "immediate"),
        ],
    },
    "skin": {
        "title": "Skin quality",
        "changeable": "high",
        "why": "Even tone and smooth texture are among the strongest cues in the research literature. "
               "The tool's photo-based skin score is crude, so trust the mirror too.",
        "actions": [
            ("Daily broad-spectrum sunscreen SPF 30+, every morning, all year", "strong", "low", "months-years"),
            ("Gentle cleanser + moisturiser; do not over-wash", "moderate", "low", "weeks"),
            ("A retinoid at night (adapalene OTC, or tretinoin by prescription) for acne, texture and "
             "ageing. Start 2-3x/week; avoid in pregnancy", "strong", "medium", "8-12 weeks"),
            ("Persistent acne, scarring or rosacea: see a dermatologist; prescription treatment "
             "works far better than product-hopping", "strong", "low", "months"),
            ("Eat plenty of colourful fruit and vegetables: carotenoids give skin a golden tone "
             "that raters read as healthy", "moderate", "low", "6-8 weeks"),
            ("Do not smoke; it is one of the clearest causes of premature facial ageing", "strong", "low", "years"),
        ],
    },
    "dimorphism": {
        "title": "Sex-typical features",
        "changeable": "medium",
        "why": "For women, more feminine face shapes rated clearly higher; for men, masculinity "
               "showed almost no link to ratings in the reference data.",
        "actions": [
            ("Men: lean out and use stubble to define the jaw, rather than chasing extreme masculinity",
             "moderate", "low", "months"),
            ("Women: brow shape, hairstyle and makeup technique strongly change how feminine a face "
             "reads", "moderate", "low", "immediate"),
        ],
    },
}

# ---------------------------------------------------------------- presentation
PRESENTATION = [
    ("Head angle: tilt your head very slightly down and look into the lens. In the reference data "
     "head pitch alone correlated ~0.5 with ratings, more than any facial measure", "moderate", "low"),
    ("Never take close selfies at arm's length: at ~30 cm, the lens makes the nose look about 30% "
     "bigger than at 1.5 m. Use a timer or a friend with the camera at 1.5-2 m", "strong", "low"),
    ("Soft light from the front or slightly above (window light). Hard overhead light deepens "
     "under-eye shadows", "moderate", "low"),
    ("Camera at or slightly above eye level; below the chin widens the jaw and neck", "moderate", "low"),
    ("Neutral expression or slight closed-mouth smile; wide open-mouth smiles rated lower in the "
     "reference data", "moderate", "low"),
    ("Keep a fresh haircut (every 3-5 weeks for short styles) and clothes that fit at the shoulders",
     "moderate", "low"),
]

# ---------------------------------------------------------------- general habits
CORE_HABITS = [
    ("Sleep 7-9 hours on a regular schedule", "moderate", "low",
     "Sleep-deprived faces are rated less attractive and less healthy (Axelsson et al., BMJ 2010)."),
    ("Resistance training 3-4x/week", "strong", "low",
     "Builds shoulder-to-waist ratio and upper-body strength cues, which strongly drive male body "
     "attractiveness, and helps facial leanness."),
    ("Daily sunscreen", "strong", "low", "Slows visible skin ageing (randomised trial, Hughes et al. 2013)."),
    ("High-protein, mostly whole-food diet at a body fat that shows your bone structure", "strong", "low", ""),
    ("Daily steps (8-10k) and some cardio", "strong", "low", "Helps fat loss and circulation (skin colour)."),
    ("Good posture: stack head over shoulders", "weak", "low",
     "Forward head posture softens the jaw-neck angle in profile."),
    ("Teeth: whitening (dentist-supervised) and straightening if needed", "moderate", "low",
     "Smile aesthetics affect first impressions."),
]

LESSER_KNOWN = [
    ("Carotenoid-rich diet (carrots, sweet potato, tomatoes, peppers, leafy greens)", "moderate", "low",
     "Raises skin yellowness within ~6-8 weeks; raters read it as healthier and more attractive than a tan "
     "(Stephen, Whitehead et al.)."),
    ("Selfie distance: shoot from 1.5 m+", "strong", "low",
     "Close lenses inflate nose size about 30% (Ward et al., JAMA Facial Plast Surg 2018)."),
    ("Treat nasal congestion / allergies / sleep apnoea", "moderate", "low",
     "Better sleep and less under-eye puffiness; chronic mouth-breathing in children is linked to longer "
     "faces. In adults it will not move bone, but breathing and sleep improve."),
    ("Heavy stubble over clean-shaven for most men", "moderate", "low",
     "Heavy stubble often rates highest in studies (Dixson & Brooks 2013), but preferences vary."),
    ("Keep brows thick; trim instead of plucking the lower edge", "weak", "low",
     "Lower, fuller brows make the eye area look deeper ('hunter eyes')."),
    ("Cold water or a cold compress in the morning", "weak", "low", "Temporarily reduces puffiness; lasts hours, not days."),
    ("Sleep on your back with your head slightly raised", "weak", "low",
     "Less morning eyelid puffiness and fewer sleep creases."),
    ("Ferritin / iron, vitamin D and thyroid check if hair is shedding", "moderate", "low",
     "Common, treatable causes of hair thinning; ask a doctor for bloodwork."),
    ("Ketoconazole 2% shampoo 2-3x/week", "weak", "low",
     "Controls dandruff and scalp inflammation; small evidence as a hair-loss adjunct."),
    ("Hair loss: talk to a doctor early about minoxidil / finasteride", "strong", "medium",
     "Both work and are most effective when started early. Prescription only; finasteride has known "
     "side effects that need to be discussed with a doctor."),
    ("Gua sha / lymphatic facial massage", "weak", "low",
     "Temporary depuffing at best; does not change fat or bone."),
]

# Popular in the community but with no evidence of lasting effect
OVERRATED = [
    ("Mewing (tongue posture) to reshape the adult jaw", "none", "low",
     "No credible evidence it changes adult bone. Good tongue posture is harmless; holding the jaw forward "
     "can cause jaw pain."),
    ("Hard-gum chewing (mastic) for a bigger jaw", "weak", "medium",
     "May enlarge masseters slightly, but can strain the jaw joint (TMJ pain, clicking)."),
    ("Canthal tilt as a key rating factor", "weak", "low",
     "In the reference data, its apparent link to ratings disappeared once head angle was controlled."),
    ("Facial exercises / 'face yoga' to slim the face", "weak", "low",
     "You cannot spot-reduce facial fat; overall fat loss is what works."),
]

# Do not do these
AVOID = [
    ("Bone smashing (hitting facial bones to 'remodel' them)",
     "No evidence; risks fractures, nerve damage, asymmetric scarring and vision damage."),
    ("DNP or other unregulated fat-loss drugs", "DNP has killed people at doses close to the 'effective' dose."),
    ("Non-prescribed steroids, SARMs, or other hormones", "Cardiovascular, liver and fertility harm; can accelerate hair loss and cause acne."),
    ("Melanotan / tanning injections, and tanning beds", "Unregulated peptides and UV beds raise skin-cancer risk."),
    ("DIY fillers, injections, 'thumb pulling' or home palate expanders", "Infection, vascular occlusion, dental and joint damage."),
    ("Crash diets or water cutting", "Makes the face gaunt, loses muscle, causes hair shedding; weight rebounds."),
]

SURGICAL_NOTE = (
    "Structural changes (chin, jaw, nose, eyelids, orthognathic surgery) are only safe with a "
    "board-certified surgeon after an in-person consultation. Get a second opinion, and prefer "
    "treating a functional issue (bite, airway) over a purely aesthetic one."
)
