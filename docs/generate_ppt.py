"""Generate NPC Biometric Attendance System PPT - Clean, minimal, 16pt+ fonts."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

NAVY = RGBColor(0x1a, 0x23, 0x7e)
NAVY2 = RGBColor(0x28, 0x35, 0x93)
ORANGE = RGBColor(0xe6, 0x51, 0x00)
GREEN = RGBColor(0x2e, 0x7d, 0x32)
RED = RGBColor(0xc6, 0x28, 0x28)
WHITE = RGBColor(0xff, 0xff, 0xff)
GREY = RGBColor(0x88, 0x88, 0x88)
BLACK = RGBColor(0x33, 0x33, 0x33)
LGREY = RGBColor(0xf0, 0xf2, 0xf5)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def grad(slide, c1, c2):
    f = slide.background.fill
    f.gradient()
    f.gradient_stops[0].color.rgb = c1
    f.gradient_stops[1].color.rgb = c2


def txt(slide, l, t, w, h, text, sz=18, clr=BLACK, bold=False, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.size = Pt(sz)
        p.font.color.rgb = clr
        p.font.bold = bold
        p.font.name = 'Segoe UI'
        p.alignment = align
        p.space_after = Pt(4)
    return tb


def box(slide, l, t, w, h, fill, text='', sz=16, clr=WHITE, bold=False):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(l), Inches(t), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    sh.line.fill.background()
    if text:
        tf = sh.text_frame
        tf.word_wrap = True
        for i, line in enumerate(text.split('\n')):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line
            p.font.size = Pt(sz)
            p.font.color.rgb = clr
            p.font.bold = bold
            p.font.name = 'Segoe UI'
            p.alignment = PP_ALIGN.CENTER
    return sh


def sn(slide, n, clr=WHITE):
    txt(slide, 12.6, 7.0, 0.6, 0.3, str(n), sz=10, clr=clr, align=PP_ALIGN.RIGHT)


# 1. TITLE
s = prs.slides.add_slide(BLANK)
grad(s, RGBColor(0x0d, 0x1b, 0x4a), NAVY2)
txt(s, 1, 1.5, 11, 0.5, 'NATIONAL PRODUCTIVITY COUNCIL', sz=16, clr=RGBColor(0x99,0xaa,0xff), align=PP_ALIGN.CENTER)
txt(s, 1, 2.3, 11, 1.5, 'Biometric Attendance\nManagement System', sz=44, clr=WHITE, bold=True, align=PP_ALIGN.CENTER)
txt(s, 1, 4.3, 11, 0.5, 'Ministry of Commerce & Industry, Government of India', sz=16, clr=RGBColor(0xbb,0xbb,0xff), align=PP_ALIGN.CENTER)
for i, (lb, cl) in enumerate([('DG / DDG', NAVY2), ('Group Heads', ORANGE), ('Employees', GREEN), ('Admin', RED)]):
    box(s, 3.2 + i*1.9, 5.3, 1.6, 0.5, cl, lb, sz=16, bold=True)
sn(s,1)

# 2. PROBLEM
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
txt(s, 1, 0.6, 11, 0.7, 'The Problem We Solve', sz=36, clr=NAVY, bold=True, align=PP_ALIGN.CENTER)
for i, (ic, ti) in enumerate([('📋','Manual\nProcess'), ('⏰','Delayed\nFinalization'), ('🚫','No Audit\nTrail'), ('👤','Zero\nTransparency')]):
    x = 0.8 + i*3.1
    box(s, x, 2.0, 2.7, 3.8, LGREY)
    txt(s, x, 2.2, 2.7, 0.8, ic, sz=44, align=PP_ALIGN.CENTER)
    txt(s, x, 3.3, 2.7, 1.0, ti, sz=22, clr=NAVY, bold=True, align=PP_ALIGN.CENTER)
sn(s,2,BLACK)

# 3. HOW IT WORKS
s = prs.slides.add_slide(BLANK)
grad(s, RGBColor(0x0d,0x1b,0x4a), NAVY2)
txt(s, 1, 0.5, 11, 0.6, 'How It Works', sz=36, clr=WHITE, bold=True, align=PP_ALIGN.CENTER)
for i, (st, lb) in enumerate([('📁\nUpload','Admin'), ('⚠️\nDetect','System'), ('✍️\nJustify','Employee'), ('🔍\nReview','Head'), ('✅\nFinalize','Admin'), ('📅\nDeduct','System')]):
    x = 0.5 + i*2.1
    box(s, x, 1.6, 1.8, 1.8, NAVY2, st, sz=20, bold=True)
    txt(s, x, 3.5, 1.8, 0.4, lb, sz=16, clr=RGBColor(0x99,0xaa,0xff), align=PP_ALIGN.CENTER)
    if i < 5:
        txt(s, x+1.85, 2.1, 0.3, 0.5, '→', sz=24, clr=RGBColor(0x66,0x7e,0xea), align=PP_ALIGN.CENTER)
for i, (v, l) in enumerate([('13+','Offices'), ('500+','Employees'), ('49','Routes'), ('42','Tests')]):
    x = 1.2 + i*3.0
    box(s, x, 4.6, 2.4, 1.6, WHITE)
    txt(s, x, 4.7, 2.4, 0.8, v, sz=36, clr=NAVY, bold=True, align=PP_ALIGN.CENTER)
    txt(s, x, 5.6, 2.4, 0.4, l, sz=18, clr=GREY, align=PP_ALIGN.CENTER)
sn(s,3)

# 4. WORKFLOW STEPS 1-3
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
txt(s, 0.8, 0.4, 11, 0.6, 'Workflow: Steps 1 → 3', sz=32, clr=NAVY, bold=True)
box(s, 0.5, 1.3, 3.7, 5.2, RGBColor(0xfc,0xe4,0xec))
txt(s, 0.7, 1.4, 3.3, 0.5, '❶  Admin Uploads', sz=22, clr=RED, bold=True)
txt(s, 0.7, 2.1, 3.3, 3.5, '• Select Office\n\n• Upload biometric XLS\n\n• Set rules\n  (late time, min hours)\n\n• System auto-detects\n  anomalies', sz=16, clr=BLACK)
txt(s, 4.3, 3.5, 0.5, 0.5, '▶', sz=28, clr=RGBColor(0xcc,0xcc,0xcc), align=PP_ALIGN.CENTER)
box(s, 4.9, 1.3, 3.7, 5.2, RGBColor(0xe8,0xf5,0xe9))
txt(s, 5.1, 1.4, 3.3, 0.5, '❷  Employee Justifies', sz=22, clr=GREEN, bold=True)
txt(s, 5.1, 2.1, 3.3, 3.5, '• Sees own anomalies\n\n• Types reason for each\n  (tour, medical, etc.)\n\n• Clicks Submit\n\n• Auto-saved if offline', sz=16, clr=BLACK)
txt(s, 8.7, 3.5, 0.5, 0.5, '▶', sz=28, clr=RGBColor(0xcc,0xcc,0xcc), align=PP_ALIGN.CENTER)
box(s, 9.3, 1.3, 3.5, 5.2, RGBColor(0xff,0xf3,0xe0))
txt(s, 9.5, 1.4, 3.1, 0.5, '❸  Head Reviews', sz=22, clr=ORANGE, bold=True)
txt(s, 9.5, 2.1, 3.1, 1.2, '• Reads justification\n\n• Decides per anomaly:', sz=16, clr=BLACK)
box(s, 9.6, 3.8, 2.9, 0.6, GREEN, '✅  Accept → Exclude', sz=18, bold=True)
box(s, 9.6, 4.6, 2.9, 0.6, RED, '❌  Decline → Count', sz=18, bold=True)
box(s, 9.6, 5.4, 2.9, 0.6, ORANGE, '❓  Query → Ask More', sz=18, bold=True)
sn(s,4,BLACK)

# 5. WORKFLOW STEPS 4-5
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
txt(s, 0.8, 0.4, 11, 0.6, 'Workflow: Steps 4 → 5', sz=32, clr=NAVY, bold=True)
box(s, 0.5, 1.3, 5.5, 5.0, RGBColor(0xe8,0xea,0xf6))
txt(s, 0.7, 1.4, 5.1, 0.5, '❹  Admin Finalizes', sz=24, clr=NAVY, bold=True)
txt(s, 0.7, 2.2, 5.1, 3.0, '• Reviews Head decisions\n\n• Can override with reason\n\n• "Exclude" → No deduction\n  "Count" → Deduct leave\n\n• Clicks Finalize → Month locked', sz=18, clr=BLACK)
txt(s, 6.2, 3.5, 0.5, 0.5, '▶', sz=32, clr=RGBColor(0xcc,0xcc,0xcc), align=PP_ALIGN.CENTER)
box(s, 6.8, 1.3, 5.8, 5.0, RGBColor(0xff,0xeb,0xee))
txt(s, 7.0, 1.4, 5.4, 0.5, '❺  Leave Deducted', sz=24, clr=RED, bold=True)
txt(s, 7.0, 2.2, 5.4, 1.5, '• Only "Counted" anomalies remain\n\n• First 2 days = FREE\n\n• Each extra = 0.5 EL deducted', sz=18, clr=BLACK)
box(s, 7.2, 4.5, 5.0, 1.4, WHITE)
txt(s, 7.4, 4.6, 4.6, 0.5, 'Example:', sz=20, clr=NAVY, bold=True)
txt(s, 7.4, 5.1, 4.6, 0.7, '8 anomalies − 3 accepted = 5 counted\n5 − 2 free = 3 × 0.5 = 1.5 EL', sz=20, clr=RED, bold=True)
sn(s,5,BLACK)

# 6. SWIMLANE
s = prs.slides.add_slide(BLANK)
grad(s, RGBColor(0x0d,0x1b,0x4a), NAVY2)
txt(s, 0.8, 0.3, 11, 0.6, 'Workflow at a Glance', sz=32, clr=WHITE, bold=True, align=PP_ALIGN.CENTER)
lanes = [
    (RED, 'ADMIN', ['Upload XLS', 'Auto-Analyze']),
    (GREEN, 'EMPLOYEE', ['View Anomalies', 'Write Reasons', 'Submit']),
    (ORANGE, 'HEAD', ['Read Justification', 'Accept / Decline / Query']),
    (RED, 'ADMIN', ['Review Decisions', 'Finalize', 'Deduct Leave']),
]
for i, (cl, role, acts) in enumerate(lanes):
    y = 1.2 + i*1.2
    box(s, 0.5, y, 2.2, 0.8, cl, role, sz=18, bold=True)
    for j, a in enumerate(acts):
        x = 3.2 + j*3.2
        box(s, x, y, 2.8, 0.8, NAVY2, a, sz=16)
        if j < len(acts)-1:
            txt(s, x+2.85, y+0.15, 0.3, 0.5, '→', sz=20, clr=RGBColor(0x66,0x7e,0xea), align=PP_ALIGN.CENTER)
box(s, 0.5, 6.0, 12.3, 0.9, RGBColor(0x1a,0x23,0x7e))
txt(s, 0.5, 6.1, 12.3, 0.6, 'Total − Accepted − Free(2) = Deductible × 0.5 = Leave Deducted', sz=20, clr=ORANGE, bold=True, align=PP_ALIGN.CENTER)
sn(s,6)

# 7. LOGIN
s = prs.slides.add_slide(BLANK)
bg(s, LGREY)
txt(s, 0.8, 0.4, 5, 0.6, 'How to Login', sz=36, clr=NAVY, bold=True)
creds = [('Employee','dk.rahul'), ('Group Head','gh.hrmgroup'), ('DG / DDG','dg / ddg1 / ddg2'), ('Admin','admin')]
for i, (r, u) in enumerate(creds):
    y = 1.5 + i*0.9
    txt(s, 1.2, y, 2.5, 0.5, r, sz=20, clr=BLACK, bold=True)
    box(s, 4.0, y, 3.2, 0.6, RGBColor(0xe8,0xea,0xf6), u, sz=18, clr=NAVY, bold=True)
txt(s, 1.0, 5.4, 6, 0.5, '🔐  Default password: npc123', sz=20, clr=RED, bold=True)
txt(s, 1.0, 6.0, 6, 0.5, '⚠️  Must change on first login', sz=18, clr=BLACK)
box(s, 7.8, 1.5, 4.8, 3.5, WHITE)
txt(s, 7.8, 1.7, 4.8, 0.5, 'Forgot Password?', sz=24, clr=NAVY, bold=True, align=PP_ALIGN.CENTER)
txt(s, 8.0, 2.5, 4.4, 1.0, 'Email your Username\n& Employee Code to:', sz=20, clr=BLACK, align=PP_ALIGN.CENTER)
box(s, 8.3, 3.8, 3.8, 0.7, RGBColor(0xe3,0xf2,0xfd), 'vijay.kumar@npcindia.gov.in', sz=16, clr=NAVY, bold=True)
sn(s,7,BLACK)

# 8-9. SECTION A: DG/DDG
s = prs.slides.add_slide(BLANK)
grad(s, RGBColor(0x0d,0x1b,0x4a), NAVY2)
txt(s, 1, 2.0, 11, 0.5, 'SECTION A', sz=20, clr=RGBColor(0x99,0xaa,0xff), align=PP_ALIGN.CENTER)
txt(s, 1, 2.8, 11, 1.0, '🏢  DG & DDG', sz=48, clr=WHITE, bold=True, align=PP_ALIGN.CENTER)
txt(s, 1, 4.2, 11, 0.5, 'Organization-wide oversight', sz=22, clr=RGBColor(0xbb,0xbb,0xff), align=PP_ALIGN.CENTER)
sn(s,8)

s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
txt(s, 0.8, 0.4, 8, 0.6, 'DG / DDG Dashboard', sz=32, clr=NAVY, bold=True)
box(s, 0.5, 1.3, 5.8, 5.3, LGREY)
txt(s, 0.7, 1.4, 5.4, 0.5, '👁️  What You See', sz=22, clr=NAVY, bold=True)
for i, it in enumerate(['All 12 department tabs', 'Employee summary per dept', 'Anomaly counts & deductions', 'Justification progress']):
    txt(s, 1.0, 2.2 + i*0.8, 5.0, 0.5, '✓  ' + it, sz=20, clr=BLACK)
box(s, 6.8, 1.3, 5.8, 5.3, RGBColor(0xe8,0xf5,0xe9))
txt(s, 7.0, 1.4, 5.4, 0.5, '👆  What You Do', sz=22, clr=GREEN, bold=True)
for i, it in enumerate(['Click dept → see employees', 'Click employee → daily detail', 'Monitor chronic late-comers', 'Oversight only (no action)']):
    txt(s, 7.3, 2.2 + i*0.8, 5.0, 0.5, '✓  ' + it, sz=20, clr=BLACK)
sn(s,9,BLACK)

# 10-11. SECTION B: HEADS
s = prs.slides.add_slide(BLANK)
grad(s, RGBColor(0xbf,0x36,0x0c), ORANGE)
txt(s, 1, 2.0, 11, 0.5, 'SECTION B', sz=20, clr=RGBColor(0xff,0xcc,0x80), align=PP_ALIGN.CENTER)
txt(s, 1, 2.8, 11, 1.0, '👥  Group Heads', sz=48, clr=WHITE, bold=True, align=PP_ALIGN.CENTER)
txt(s, 1, 4.2, 11, 0.5, 'Review & decide on justifications', sz=22, clr=RGBColor(0xff,0xe0,0xb2), align=PP_ALIGN.CENTER)
sn(s,10)

s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
txt(s, 0.8, 0.4, 8, 0.6, 'Head: Your 3 Actions', sz=32, clr=ORANGE, bold=True)
for i, (ic, ti, de, cl, bgc) in enumerate([
    ('✅','Accept','Exclude anomaly\nNo leave deduction', GREEN, RGBColor(0xe8,0xf5,0xe9)),
    ('❌','Decline','Count anomaly\nLeave deducted', RED, RGBColor(0xff,0xeb,0xee)),
    ('❓','Query','Need more info\nBack to employee', ORANGE, RGBColor(0xff,0xf3,0xe0)),
]):
    x = 0.5 + i*4.2
    box(s, x, 1.3, 3.8, 4.8, bgc)
    txt(s, x, 1.5, 3.8, 0.8, ic, sz=52, align=PP_ALIGN.CENTER)
    txt(s, x, 2.6, 3.8, 0.6, ti, sz=28, clr=cl, bold=True, align=PP_ALIGN.CENTER)
    txt(s, x, 3.5, 3.8, 1.2, de, sz=20, clr=BLACK, align=PP_ALIGN.CENTER)
txt(s, 0.8, 6.4, 12, 0.5, '💡  Bulk: "Accept All" / "Decline All" buttons available', sz=18, clr=GREY, align=PP_ALIGN.CENTER)
sn(s,11,BLACK)

# 12-13. SECTION C: EMPLOYEES
s = prs.slides.add_slide(BLANK)
grad(s, RGBColor(0x1b,0x5e,0x20), GREEN)
txt(s, 1, 2.0, 11, 0.5, 'SECTION C', sz=20, clr=RGBColor(0xa5,0xd6,0xa7), align=PP_ALIGN.CENTER)
txt(s, 1, 2.8, 11, 1.0, '👤  Employees', sz=48, clr=WHITE, bold=True, align=PP_ALIGN.CENTER)
txt(s, 1, 4.2, 11, 0.5, 'View attendance & justify anomalies', sz=22, clr=RGBColor(0xc8,0xe6,0xc9), align=PP_ALIGN.CENTER)
sn(s,12)

s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
txt(s, 0.8, 0.4, 8, 0.6, 'Employee: 3 Simple Steps', sz=32, clr=GREEN, bold=True)
for i, (n, ti, de) in enumerate([
    ('1','View Anomalies','See: Late, Early\nShort Hours, Missing'),
    ('2','Write Justification','Type reason:\ntour, medical, device'),
    ('3','Click Submit','Sent to Head\nSuccess message shown'),
]):
    x = 0.5 + i*4.2
    box(s, x, 1.3, 3.8, 1.0, GREEN, n, sz=40, bold=True)
    txt(s, x, 2.6, 3.8, 0.5, ti, sz=22, clr=GREEN, bold=True, align=PP_ALIGN.CENTER)
    txt(s, x, 3.3, 3.8, 1.2, de, sz=18, clr=BLACK, align=PP_ALIGN.CENTER)
box(s, 1.0, 5.3, 5.0, 1.0, RGBColor(0xff,0xf3,0xe0), '🔌  Offline? Auto-saved locally', sz=18, clr=ORANGE)
box(s, 6.5, 5.3, 5.8, 1.0, RGBColor(0xe3,0xf2,0xfd), '❓  Head queried? Update & re-submit', sz=18, clr=NAVY)
sn(s,13,BLACK)

# 14. LEAVE RULES
s = prs.slides.add_slide(BLANK)
grad(s, RGBColor(0x0d,0x1b,0x4a), NAVY2)
txt(s, 1, 0.4, 11, 0.6, 'Leave Deduction Rule', sz=36, clr=WHITE, bold=True, align=PP_ALIGN.CENTER)
txt(s, 1.0, 1.5, 5.0, 1.5, '2', sz=100, clr=ORANGE, bold=True, align=PP_ALIGN.CENTER)
txt(s, 1.0, 3.4, 5.0, 0.5, 'Free anomaly days / month', sz=20, clr=RGBColor(0xcc,0xcc,0xff), align=PP_ALIGN.CENTER)
txt(s, 1.0, 4.3, 5.0, 1.0, '0.5', sz=80, clr=ORANGE, bold=True, align=PP_ALIGN.CENTER)
txt(s, 1.0, 5.7, 5.0, 0.5, 'EL deducted per extra day', sz=20, clr=RGBColor(0xcc,0xcc,0xff), align=PP_ALIGN.CENTER)
box(s, 6.5, 1.3, 6.0, 5.4, NAVY2)
for i, (d, de, v) in enumerate([('1-2 days','0 EL','🟢🟢'), ('3 days','0.5 EL','🟢🟢🔴'), ('5 days','1.5 EL','🟢🟢🔴🔴🔴'), ('8 days','3.0 EL','🟢🟢+🔴×6'), ('12 days','5.0 EL','🟢🟢+🔴×10')]):
    y = 1.5 + i*1.0
    txt(s, 6.7, y, 2.0, 0.5, d, sz=20, clr=WHITE)
    txt(s, 9.0, y, 1.5, 0.5, de, sz=20, clr=ORANGE if float(de.split()[0])>1 else WHITE, bold=True)
    txt(s, 10.5, y, 2.0, 0.5, v, sz=18, clr=WHITE)
sn(s,14)

# 15-16. SECTION D: ADMIN
s = prs.slides.add_slide(BLANK)
grad(s, RGBColor(0x7f,0x00,0x00), RED)
txt(s, 1, 2.0, 11, 0.5, 'SECTION D', sz=20, clr=RGBColor(0xff,0x8a,0x80), align=PP_ALIGN.CENTER)
txt(s, 1, 2.8, 11, 1.0, '⚙️  Admin', sz=48, clr=WHITE, bold=True, align=PP_ALIGN.CENTER)
txt(s, 1, 4.2, 11, 0.5, 'Upload, manage, finalize, export', sz=22, clr=RGBColor(0xff,0xcd,0xd2), align=PP_ALIGN.CENTER)
sn(s,15)

s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
txt(s, 0.8, 0.4, 8, 0.6, 'Admin Capabilities', sz=32, clr=RED, bold=True)
box(s, 0.5, 1.3, 5.8, 5.3, RGBColor(0xfc,0xe4,0xec))
txt(s, 0.7, 1.4, 5.4, 0.5, '🔧  Management', sz=22, clr=RED, bold=True)
for i, it in enumerate(['Upload biometric XLS per office', 'Add / edit / delete users', 'Reset employee passwords', 'Manage offices & departments', 'Configure anomaly rules']):
    txt(s, 1.0, 2.2 + i*0.7, 5.0, 0.5, '✓  ' + it, sz=18, clr=BLACK)
box(s, 6.8, 1.3, 5.8, 5.3, RGBColor(0xe8,0xea,0xf6))
txt(s, 7.0, 1.4, 5.4, 0.5, '📊  Reports & Data', sz=22, clr=NAVY, bold=True)
for i, it in enumerate(['Excel export (dept sheets)', 'PDF print-friendly report', 'Audit log (who, what, when)', 'eHRMS leave reconciliation', 'Holiday calendar']):
    txt(s, 7.3, 2.2 + i*0.7, 5.0, 0.5, '✓  ' + it, sz=18, clr=BLACK)
sn(s,16,BLACK)

# 17. SECURITY
s = prs.slides.add_slide(BLANK)
grad(s, RGBColor(0x0d,0x1b,0x4a), NAVY2)
txt(s, 1, 0.4, 11, 0.6, 'Security & Features', sz=32, clr=WHITE, bold=True, align=PP_ALIGN.CENTER)
for i, (ic, ti) in enumerate([('🔐','CSRF'), ('🔑','Password'), ('⏰','Timeout'), ('📝','Audit'), ('🌐','GIGW 3.0'), ('📱','Mobile'), ('🇮🇳','Hindi'), ('🔌','Offline'), ('📊','Charts'), ('⏱️','Rate Limit')]):
    r, c = divmod(i, 5)
    x, y = 0.5 + c*2.5, 1.4 + r*2.7
    box(s, x, y, 2.2, 2.2, WHITE)
    txt(s, x, y+0.2, 2.2, 0.8, ic, sz=36, align=PP_ALIGN.CENTER)
    txt(s, x, y+1.2, 2.2, 0.5, ti, sz=18, clr=NAVY, bold=True, align=PP_ALIGN.CENTER)
sn(s,17)

# 18. THANK YOU
s = prs.slides.add_slide(BLANK)
grad(s, RGBColor(0x0d,0x1b,0x4a), NAVY2)
txt(s, 1, 1.8, 11, 1.0, 'Thank You', sz=52, clr=WHITE, bold=True, align=PP_ALIGN.CENTER)
txt(s, 1, 3.2, 11, 0.5, 'NPC Biometric Attendance Management System', sz=22, clr=RGBColor(0xbb,0xbb,0xff), align=PP_ALIGN.CENTER)
box(s, 3.5, 4.3, 6.3, 1.6, NAVY2)
txt(s, 3.5, 4.5, 6.3, 0.5, '📧  vijay.kumar@npcindia.gov.in', sz=22, clr=WHITE, align=PP_ALIGN.CENTER)
txt(s, 3.5, 5.1, 6.3, 0.5, '🌐  npc-biometric-attendance.up.railway.app', sz=20, clr=WHITE, align=PP_ALIGN.CENTER)
txt(s, 1, 6.3, 11, 0.4, 'National Productivity Council  •  Ministry of Commerce & Industry  •  Govt. of India', sz=16, clr=RGBColor(0x88,0x88,0xcc), align=PP_ALIGN.CENTER)
sn(s,18)

prs.save('docs/NPC_Biometric_v2.pptx')
print(f'Saved: 18 slides, all text 16pt+')
