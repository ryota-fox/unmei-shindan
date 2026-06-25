"""
Vercel Python Function: /api/generate-pdf
POST body: { "code": "FX", "rank": "A", "legendRate": 88, "norm": {...} }
Response: PDF binary (application/pdf)
"""

import json, io, base64
from datetime import date
from http.server import BaseHTTPRequestHandler

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# フォント登録
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))

W, H = A4

# ===== カラーテーマ =====
KG_COLORS = {
    'dominion':  {'bg':(0.04,0.04,0.06),'bg2':(0.07,0.07,0.10),'accent':(0.79,0.66,0.30),'sub':(0.48,0.38,0.19),'text':(0.90,0.85,0.80),'muted':(0.65,0.60,0.55)},
    'resonance': {'bg':(0.04,0.05,0.08),'bg2':(0.06,0.08,0.12),'accent':(0.36,0.68,0.89),'sub':(0.18,0.42,0.63),'text':(0.85,0.90,0.95),'muted':(0.55,0.62,0.70)},
    'creation':  {'bg':(0.05,0.04,0.08),'bg2':(0.08,0.06,0.12),'accent':(0.65,0.41,0.74),'sub':(0.42,0.20,0.51),'text':(0.88,0.82,0.93),'muted':(0.58,0.52,0.65)},
    'growth':    {'bg':(0.04,0.06,0.04),'bg2':(0.06,0.09,0.06),'accent':(0.34,0.84,0.55),'sub':(0.12,0.52,0.29),'text':(0.82,0.92,0.84),'muted':(0.52,0.62,0.54)},
}

MARGIN = 28
FS = {'title':22,'heading':13,'body':11.5,'small':10,'label':9,'footer':8}

def get_tier(rate):
    if rate < 20: return 'E'
    if rate < 40: return 'D'
    if rate < 60: return 'C'
    if rate < 80: return 'B'
    if rate < 95: return 'A'
    return 'S'

RANK_TITLES = {'E':'眠れる才能','D':'覚醒予備軍','C':'成長者','B':'覚醒者','A':'英雄候補','S':'LEGEND候補者'}

TIER_MSGS = {
    'E': {'opening':'あなたの才能は、まだ眠っています。でも「眠っている」ということは、必ず目覚める可能性があるということ。今ここにいることが、すでに覚醒への第一歩です。',
          'final':'才能の眠りから覚める瞬間は、突然やってきます。この攻略書を繰り返し読み、一つずつ実践してください。'},
    'D': {'opening':'あなたの中に、確かに「何か」が芽生えています。覚醒まであと一歩。正しい方向に向ければ、ポテンシャルは一気に開花します。',
          'final':'覚醒のエネルギーはすでにあなたの中にあります。あとは「一歩」を踏み出すだけ。'},
    'C': {'opening':'あなたは確実に成長の道を歩んでいます。自分のタイプを知り、強みを活かし始めている証拠です。',
          'final':'一つずつ積み重ねてきた力は、必ず花開きます。ここからが本当の加速期です。'},
    'B': {'opening':'あなたはすでに覚醒しています。自分の強みを理解し、活かす術を身につけています。',
          'final':'LEGENDまでのラストスパートです。あなたならできます。'},
    'A': {'opening':'あなたはすでに英雄候補です。普通の人が見えていないものが見えて、やらないことをやってきた結果です。',
          'final':'最終条件さえ満たせば、LEGENDへの扉は開きます。このギルドはあなたの覚醒を確信しています。'},
    'S': {'opening':'あなたはLEGENDの扉の前に立っています。これは選ばれた人間だけが辿り着ける場所です。',
          'final':'あなたはもうLEGENDです。あとは宣言するだけ。あなたの存在が、次の誰かの地図になります。'},
}

# ===== タイプデータ（FXのみ — 後で全16タイプに展開）=====
TYPE_DATA = {
    'FX': {
        'name':'フィクサー','kingdom':'dominion','beast':'漆黒の狼',
        'legendJob':'運命編纂者','darkJob':'操り人形師',
        'outsiderVoice':['「冷静だよね」','「何考えてるかわからない」','「頼りになる」','「本気を見せない」','「いつの間にか場を仕切ってる」','「裏で全部わかってそう」','「あなたに任せれば安心」'],
        'outsiderDesc':{
            '「冷静だよね」':'感情を「内側で処理してから表に出す」習慣があるからです。',
            '「何考えてるかわからない」':'思考は常に数手先を読んでいます。周囲が追いつけていないだけで、行動には必ず理由があります。',
            '「頼りになる」':'誰かが困る前に気づき、動いています。「言わなくてもわかってくれる人」——それがフィクサーです。',
            '「本気を見せない」':'本気を見せることで「期待される」のが怖いのかもしれません。でも、本気を出したとき、周囲は必ず動かされます。',
            '「いつの間にか場を仕切ってる」':'意識していないのに、自然とそうなっています。「場の設計力」が無意識に機能しているからです。',
            '「裏で全部わかってそう」':'情報を持っているだけでなく、その意味まで読んでいます。その力が「フィクサー」の核心です。',
            '「あなたに任せれば安心」':'最高の褒め言葉です。信頼は一日では作れません。あなたが積み重ねてきた行動の証です。',
        },
        'essence':'フィクサーの本質を一言で表すなら「安心を、支配によって守ろうとする人」です。\n\n幼い頃から、あなたは場の空気を読むことが得意でした。家族の機嫌、教室の雰囲気、グループの力関係——他の子がまだ気づいていない段階で、あなたはすでに「この場はどう動くか」を把握していました。\n\nそれは才能でしたが、同時に重荷でもありました。場をコントロールしていないと不安になる。全体が見えているからこそ、誰かの無計画な行動にハラハラする。気づけば「自分が調整しなければ」という役割を、誰に頼まれたわけでもなく引き受けていました。\n\n他のタイプから見ると、フィクサーは「何を考えているかわからない人」に映ります。感情をあまり表に出さず、いつも一歩引いたところから全体を見ている。でもその内側には、誰よりも強い「誰かの役に立ちたい」という感情が流れています。\n\n本人がまだ気づいていない最大の強みは「場の設計力」です。フィクサーがいるだけで、なぜかその場が安定する。これはスキルではなく、存在そのものが持つ力です。',
        'awakening':[
            ('条件1','観察を行動に変える',['今週：分析した内容を誰かに言葉にして伝える','1ヶ月：小さな提案を一つ実行する（7割の完成度でOK）','3ヶ月：「観察→分析→行動」のサイクルを週1回以上回す'],'「もう少し情報が揃ってから」と先送りすること。'),
            ('条件2','誰かのために考える',['今週：見返りを求めず、黙って誰かのために行動する','1ヶ月：評価されなくていい貢献を一つ作る','3ヶ月：「自分の利益」と「相手の利益」を切り離して考える'],'「相手のため」と思いながら実はコントロール欲が動機になっていること。'),
            ('条件3','感情を切り捨てない',['今週：「この人は今どんな気持ちか」を感じる練習をする','1ヶ月：自分の感情に名前をつけ、毎日一回書き出す','3ヶ月：感情と論理を統合した判断ができるようになる'],'感情を「ノイズ」として排除しすぎること。感情は大切な情報です。'),
            ('条件4','裏方であることを楽しむ',['今週：誰にも気づかれない形で誰かの役に立つことをする','1ヶ月：「ありがとう」なしに動けた行動を記録する','3ヶ月：承認なしに動ける場面が増え、余裕が生まれる'],'承認を求める気持ちが強くなりすぎること。LEGEND覚醒の最大の壁です。'),
            ('条件5','少数の信頼できる相手と深く組む',['今週：信頼できる3人を選び、少し本音を見せる','1ヶ月：信頼する相手に「助けてほしい」と言える場面を作る','3ヶ月：信頼関係が仕事・人生の土台になっている感覚が生まれる'],'「頼ること」への抵抗。フィクサーにとって頼ることは覚醒の証です。'),
        ],
        'love':[
            ('フィクサーの恋愛の特徴','フィクサーの恋愛は「観察」から始まります。好きな人ができても、すぐに動くことはしません。相手のパターンを読み、どんな言葉に反応するかを把握し、「この人はどういう人間か」を理解してからようやく一手を打ちます。この慎重さは強みですが、「タイミングを逃す」という弱点にもなります。'),
            ('惹かれやすいタイプ','フィクサーが本能的に惹かれるのは「感情豊かで、自分の知らない世界を持っている人」です。論理で世界を構築するフィクサーは、感性で動く人に強く惹きつけられます。また「自分のことを見透かしてくる人」にも惹かれます。普段は見せない本音を、なぜか引き出してくれる存在——それがフィクサーにとって特別な人です。'),
            ('最初のアプローチ','フィクサーの最も自然なアプローチは「さりげない気遣い」です。大げさなアピールは似合いません。相手が困っているときにさりげなく助ける、小さなことを後日覚えていて触れる——こういった行動がフィクサーの魅力を最大限に引き出します。\nやってはいけないこと：「相手を試す」行動です。フィクサーは無意識に相手を試してしまいますが、相手はこれを感じ取り、壁を作ることがあります。'),
            ('関係が深まるタイミング','フィクサーとの関係は「あなたが本音を話した瞬間」に一気に深まります。普段感情を見せないフィクサーが、ふとした瞬間に弱さや本音を見せたとき——相手はその瞬間を特別なものとして覚えています。「自分から先に見せる」勇気がフィクサーの恋愛を次のステージへ進める鍵です。'),
            ('長続きの秘訣','フィクサーの恋愛が長続きする条件は「完全にリラックスできる相手かどうか」です。常に場を読み、気を遣い、状況を管理しているフィクサーにとって「考えなくていい時間」は何より貴重です。あなたのペースを乱さず、でも停滞しないように背中を押してくれる人——そんな存在が最高のパートナーです。'),
        ],
        'work':[
            ('1. 経営企画・事業開発','組織全体を俯瞰し、中長期の戦略を設計する役割。表に出ず、経営者の「右腕」として機能するポジションは、フィクサーが最も力を発揮する場所です。'),
            ('2. プロデューサー・ディレクター','コンテンツ・プロダクト・イベントなど「全体を設計して動かす」役割。個々のパーツよりも全体の流れを管理することが得意なフィクサーに最適です。'),
            ('3. コンサルタント・アドバイザー','クライアントの状況を分析し、最適解を提示する仕事。表舞台に出ずに影響力を行使できる点が、フィクサーの性質と完全に一致します。'),
            ('4. 編集者・キュレーター','情報や素材を整理し、価値ある形に再構成する役割。フィクサーの「本質を見抜く目」が最大限に活きます。'),
            ('5. チームリーダー・PM','人と情報とタスクを統合しプロジェクトを成功に導く役割。「静かに引っ張る」リーダーシップがフィクサーの真骨頂です。'),
        ],
        'workRelations':[
            ('【上司へ】','意図を読んだ上で一度確認してから動く習慣が信頼を高めます。先回りしすぎて空回りになることも。「確認してから動く」を意識してください。'),
            ('【部下へ】','フィクサーにとっての「当然」は他の人には高すぎる基準かもしれません。「任せる」ことが影響力を広げます。'),
            ('【同僚へ】','「今これを考えている」を意図的に共有するだけで、周囲との信頼関係が大きく変わります。'),
        ],
        'career':[
            ('3年後のゴール','「この人に頼めば間違いない」という評判を特定の領域で確立する。専門性と信頼性の両方を持つ存在になること。'),
            ('5年後のゴール','一つのプロジェクトや組織で「なくてはならない存在」になる。あなたがいることで結果が変わると周囲が実感している状態。'),
            ('10年後のゴール','複数の領域・組織にまたがる影響力を持つ。あなたが動かした人・組織・プロジェクトが社会的な価値を生み出している。'),
        ],
        'money':[
            ('収入の作り方（3選）','1. コンサルティング・顧問契約\nフィクサーの「全体を見る力」はそのままビジネスになります。月額顧問契約は時間と知識を最も効率よく収益化できる形です。\n\n2. 紹介・仲介ビジネス\n「誰と誰を繋げれば価値が生まれるか」を見抜く力は、人材紹介・不動産・M&Aなど繋ぐビジネスに直結します。\n\n3. 情報・コンテンツビジネス\n蓄積してきた知識を言語化・体系化し販売する。noteやオンライン講座など一度作れば繰り返し収益を生む仕組みと相性抜群です。'),
            ('お金に関する「無意識のブレーキ」','フィクサーが最も持ちやすいブレーキは「表に出ることへの抵抗」です。「黙っていてもわかってもらえるはず」——この思いが最大の収入の壁になっています。\n\n解除の方法：「伝えることは相手への情報提供だ」と定義し直すこと。あなたの価値を知らない人は単純に「情報を持っていない」だけです。'),
            ('5年後の経済的自由へのアクション','今月：自分の「無形資産」（人脈・知識・信頼）をリスト化する\n3ヶ月以内：コンサルまたは紹介ビジネスを身近な人への小さな提供から始める\n1年以内：月収入の10〜20%を自動積立に回す仕組みを作る\n5年後：複数収入源が機能し、どれか一つが止まっても揺らがない構造を持つ'),
        ],
        'legendCondition':'LEGEND「運命編纂者」への最終条件：自分が関わったことを、誰にも気づかれなくても良いと思えるようになること。\n\nフィクサーの真の力は「見えないところで全体を動かす」ことにあります。承認や評価を必要としなくなったとき、あなたの影響力は最大化されます。\n\n気づかれなくていい。評価されなくていい。でも、あなたが動いたことで、確かに何かが変わった——その事実だけで十分だと思えるとき、フィクサーは「運命編纂者」になります。',
    }
}

# ===== PDF描画ヘルパー =====
class PDFBuilder:
    def __init__(self, col):
        self.col = col
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4)
        self.page_num = [1]
        self.LEADING = FS['body'] * 1.75

    def bg(self):
        self.c.setFillColorRGB(*self.col['bg'])
        self.c.rect(0,0,W,H,fill=1,stroke=0)

    def hline(self, y, lw=0.3):
        self.c.setStrokeColorRGB(*self.col['accent'])
        self.c.setLineWidth(lw)
        self.c.line(MARGIN, y, W-MARGIN, y)

    def footer(self, type_name, rank, rate):
        self.hline(20, lw=0.2)
        self.c.setFont('HeiseiKakuGo-W5', FS['footer'])
        self.c.setFillColorRGB(*self.col['muted'])
        self.c.drawString(MARGIN, 13, f'運命職業診断 人生攻略書　{type_name} / {rank}ランク / LEGEND{rate}%')
        self.c.setFillColorRGB(*self.col['accent'])
        self.c.drawRightString(W-MARGIN, 13, str(self.page_num[0]))

    def chapter_header(self, num, title):
        self.bg()
        self.hline(H-24, lw=0.6)
        self.c.setFont('HeiseiKakuGo-W5', FS['label'])
        self.c.setFillColorRGB(*self.col['sub'])
        self.c.drawString(MARGIN, H-19, num)
        self.c.setFont('HeiseiMin-W3', FS['title'])
        self.c.setFillColorRGB(*self.col['accent'])
        self.c.drawString(MARGIN, H-46, title)
        self.hline(H-54, lw=0.4)
        return H - 72

    def draw_text(self, text, x, y, size=None, leading=None, color=None):
        if size is None: size = FS['body']
        if leading is None: leading = self.LEADING
        if color is None: color = self.col['text']
        cpl = max(18, min(int((W - MARGIN*2 - (x-MARGIN)) / (size * 0.57)), 38))
        self.c.setFont('HeiseiKakuGo-W5', size)
        self.c.setFillColorRGB(*color)
        to = self.c.beginText(x, y)
        to.setFont('HeiseiKakuGo-W5', size)
        to.setFillColorRGB(*color)
        to.setLeading(leading)
        lines = []
        for para in text.split('\n'):
            if not para.strip():
                lines.append('')
            else:
                for i in range(0, max(1,len(para)), cpl):
                    lines.append(para[i:i+cpl])
        for line in lines:
            to.textLine(line)
        self.c.drawText(to)
        return y - len(lines) * leading

    def section_heading(self, text, y):
        self.c.setFont('HeiseiKakuGo-W5', FS['heading'])
        self.c.setFillColorRGB(*self.col['accent'])
        self.c.drawString(MARGIN, y, '▶ ' + text)
        return y - FS['heading'] - 8

    def check_page(self, y, need, type_name, rank, rate, ch_num=None, ch_title=None):
        if y < need + 36:
            self.footer(type_name, rank, rate)
            self.c.showPage()
            self.page_num[0] += 1
            if ch_num and ch_title:
                return self.chapter_header(ch_num, ch_title + '（続き）')
            else:
                self.bg()
                return H - 40
        return y

    def new_page(self, type_name, rank, rate, ch_num=None, ch_title=None):
        self.footer(type_name, rank, rate)
        self.c.showPage()
        self.page_num[0] += 1
        if ch_num and ch_title:
            return self.chapter_header(ch_num, ch_title)
        self.bg()
        return H - 40

    def save(self):
        self.c.save()
        self.buf.seek(0)
        return self.buf.read()


def generate_pdf(code, rank, legend_rate, norm):
    td = TYPE_DATA.get(code)
    if not td:
        raise ValueError(f'Type {code} not found')

    col = KG_COLORS.get(td['kingdom'], KG_COLORS['dominion'])
    tier = get_tier(legend_rate)
    tm = TIER_MSGS[tier]
    rank_title = RANK_TITLES.get(rank, '英雄候補')
    b = PDFBuilder(col)
    tn = f"{code} {td['name']}"
    kg_names = {'dominion':'支配王国','resonance':'共鳴王国','creation':'創造王国','growth':'成長王国'}
    kg_themes = {'dominion':'世界は動かすもの','resonance':'人は一人で生きられない','creation':'世界は創るもの','growth':'昨日の自分を超えろ'}
    kg = kg_names.get(td['kingdom'],'支配王国')
    kgt = kg_themes.get(td['kingdom'],'')
    LEADING = b.LEADING

    # ===== P1: 表紙 =====
    b.bg()
    b.c.setStrokeColorRGB(*col['accent']); b.c.setLineWidth(1.2)
    b.c.rect(8,8,W-16,H-16,fill=0)
    b.c.setLineWidth(0.3); b.c.rect(13,13,W-26,H-26,fill=0)
    b.c.setFillColorRGB(*col['bg2' if 'bg2' in col else 'bg'])
    b.c.rect(0,H-110,W,110,fill=1,stroke=0)
    b.c.setStrokeColorRGB(*col['accent']); b.c.setLineWidth(0.8)
    b.c.line(0,H-110,W,H-110)
    b.c.setFont('HeiseiKakuGo-W5',9); b.c.setFillColorRGB(*col['sub'])
    b.c.drawCentredString(W/2,H-30,'人 生 攻 略 ギ ル ド')
    b.c.setFont('HeiseiMin-W3',26); b.c.setFillColorRGB(*col['accent'])
    b.c.drawCentredString(W/2,H-62,'運命職業診断')
    b.c.setFont('HeiseiKakuGo-W5',10); b.c.setFillColorRGB(*col['muted'])
    b.c.drawCentredString(W/2,H-82,'完 全 版  —  人 生 攻 略 書')
    b.hline(H-120,lw=0.6)
    b.c.setFont('HeiseiKakuGo-W5',18); b.c.setFillColorRGB(*col['sub'])
    b.c.drawCentredString(W/2,H-148,code)
    b.c.setFont('HeiseiMin-W3',42); b.c.setFillColorRGB(*col['accent'])
    b.c.drawCentredString(W/2,H-196,td['name'])
    b.c.setFont('HeiseiKakuGo-W5',11); b.c.setFillColorRGB(*col['muted'])
    b.c.drawCentredString(W/2,H-216,f'守護獣：{td["beast"]}　｜　{kg}「{kgt}」')
    b.c.setFont('HeiseiKakuGo-W5',10.5); b.c.setFillColorRGB(*col['text'])
    b.c.drawCentredString(W/2,H-234,f'LEGEND職：{td["legendJob"]}　　闇落ち職：{td["darkJob"]}')
    b.hline(H-248,lw=0.6)
    for i,(label,val,sub) in enumerate([('現在ランク',rank,rank_title),('LEGEND到達率',f'{legend_rate}%',''),('覚醒率',str(round(norm.get('growth',0)*.30+norm.get('action',0)*.25+norm.get('analysis',0)*.20+norm.get('empathy',0)*.15+norm.get('creation',0)*.10)),'')]):
        cx=85+i*145
        b.c.setFont('HeiseiKakuGo-W5',9); b.c.setFillColorRGB(*col['muted'])
        b.c.drawCentredString(cx,H-268,label)
        b.c.setFont('HeiseiMin-W3',32); b.c.setFillColorRGB(*col['accent'])
        b.c.drawCentredString(cx,H-304,val)
        if sub:
            b.c.setFont('HeiseiKakuGo-W5',8.5); b.c.setFillColorRGB(*col['sub'])
            b.c.drawCentredString(cx,H-316,sub)
    b.hline(H-328,lw=0.4)
    abilities=[('支配力','domination'),('分析力','analysis'),('行動力','action'),('共感力','empathy'),('成長力','growth'),('創造力','creation'),('守護力','guardian')]
    b.c.setFont('HeiseiKakuGo-W5',9); b.c.setFillColorRGB(*col['muted'])
    b.c.drawCentredString(W/2,H-344,'A B I L I T Y  S T A T U S')
    bx,by,bw,bh=72,H-362,W-144,9
    for aname,akey in abilities:
        val=norm.get(akey,0)
        b.c.setFont('HeiseiKakuGo-W5',9.5); b.c.setFillColorRGB(*col['muted'])
        b.c.drawString(bx-48,by+1,aname)
        b.c.setFillColorRGB(0.10,0.10,0.16); b.c.roundRect(bx,by-2,bw,bh,2,fill=1,stroke=0)
        b.c.setFillColorRGB(*col['accent']); b.c.roundRect(bx,by-2,max(3,bw*val/100),bh,2,fill=1,stroke=0)
        b.c.setFont('HeiseiKakuGo-W5',9.5); b.c.setFillColorRGB(*col['accent'])
        b.c.drawString(bx+bw+6,by+1,str(val)); by-=17
    b.hline(H-490,lw=0.3)
    b.c.setFont('HeiseiKakuGo-W5',8.5); b.c.setFillColorRGB(*col['muted'])
    b.c.drawCentredString(W/2,H-506,f'{date.today().strftime("%Y年%m月%d日")} 発行　｜　このPDFはあなた専用の個別コンテンツです')
    b.footer(tn,rank,legend_rate); b.c.showPage(); b.page_num[0]+=1

    # ===== P2: 周囲から言われていること =====
    y = b.chapter_header('OPENING','あなたが周囲から言われていること')
    b.c.setFont('HeiseiKakuGo-W5',FS['small']); b.c.setFillColorRGB(*col['muted'])
    b.c.drawString(MARGIN,y,'心当たりがある言葉は、あなたが「フィクサー」である証拠です。'); y-=22
    for voice in td['outsiderVoice']:
        desc = td['outsiderDesc'].get(voice,'')
        desc_lines=[]
        for i in range(0,max(1,len(desc)),36): desc_lines.append(desc[i:i+36])
        vH=FS['heading']+6+len(desc_lines)*(FS['small']*1.65)+28
        y=b.check_page(y,vH,tn,rank,legend_rate,'OPENING','あなたが周囲から言われていること')
        b.c.setFillColorRGB(0.09,0.08,0.05); b.c.setStrokeColorRGB(*col['accent']); b.c.setLineWidth(0.5)
        b.c.roundRect(MARGIN-2,y-vH+14,W-MARGIN*2+4,vH-4,3,fill=1,stroke=1)
        b.c.setFont('HeiseiMin-W3',FS['heading']); b.c.setFillColorRGB(*col['accent'])
        b.c.drawString(MARGIN+8,y,voice); ty=y-FS['heading']-6
        for dl in desc_lines:
            b.c.setFont('HeiseiKakuGo-W5',FS['small']); b.c.setFillColorRGB(*col['muted'])
            b.c.drawString(MARGIN+8,ty,dl); ty-=FS['small']*1.65
        y=ty-10
    b.footer(tn,rank,legend_rate); b.c.showPage(); b.page_num[0]+=1

    # ===== P3: タイプの本質 =====
    y=b.chapter_header('CHAPTER 1','あなたの本質')
    for para in td['essence'].split('\n'):
        if not para.strip(): y-=6; continue
        need=(len(para)//36+2)*LEADING
        y=b.check_page(y,need,tn,rank,legend_rate,'CHAPTER 1','あなたの本質')
        y=b.draw_text(para,MARGIN,y); y-=6
    b.footer(tn,rank,legend_rate); b.c.showPage(); b.page_num[0]+=1

    # ===== P4-5: LEGENDロードマップ =====
    y=b.chapter_header('CHAPTER 2','LEGENDロードマップ — 5条件')
    b.c.setFont('HeiseiKakuGo-W5',FS['small']); b.c.setFillColorRGB(*col['muted'])
    b.c.drawString(MARGIN,y,'5つの条件は順番通りでなくて構いません。今の自分に最も近い条件から始めてください。'); y-=20
    for num,title,steps,pitfall in td['awakening']:
        sH=26+len(steps)*LEADING+(len(pitfall)//36+1)*(FS['small']*1.6)+24
        y=b.check_page(y,sH,tn,rank,legend_rate,'CHAPTER 2','LEGENDロードマップ')
        b.c.setFillColorRGB(0.10,0.09,0.04); b.c.setStrokeColorRGB(*col['accent']); b.c.setLineWidth(0.6)
        b.c.roundRect(MARGIN-2,y-22,W-MARGIN*2+4,26,2,fill=1,stroke=1)
        b.c.setFont('HeiseiKakuGo-W5',FS['small']); b.c.setFillColorRGB(*col['sub'])
        b.c.drawString(MARGIN+6,y-8,num)
        b.c.setFont('HeiseiKakuGo-W5',FS['heading']); b.c.setFillColorRGB(*col['accent'])
        b.c.drawString(MARGIN+52,y-8,title); y-=30
        for step in steps:
            b.c.setFont('HeiseiKakuGo-W5',FS['body']); b.c.setFillColorRGB(*col['text'])
            b.c.drawString(MARGIN+4,y,'▸  '+step); y-=LEADING
        y-=4
        pfl='⚠ よくある挫折：'+pitfall
        for i in range(0,max(1,len(pfl)),38):
            b.c.setFont('HeiseiKakuGo-W5',FS['small']); b.c.setFillColorRGB(0.80,0.38,0.22)
            b.c.drawString(MARGIN+4,y,pfl[i:i+38]); y-=FS['small']*1.6
        y-=14
    b.footer(tn,rank,legend_rate); b.c.showPage(); b.page_num[0]+=1

    # ===== P6: 恋愛攻略 =====
    y=b.chapter_header('CHAPTER 3','恋愛攻略ガイド')
    for title,body in td['love']:
        lc=sum(len(p)//36+1 for p in body.split('\n'))
        need=FS['heading']+10+lc*LEADING+14
        y=b.check_page(y,need,tn,rank,legend_rate,'CHAPTER 3','恋愛攻略')
        y=b.section_heading(title,y); y=b.draw_text(body,MARGIN,y); y-=12
    b.footer(tn,rank,legend_rate); b.c.showPage(); b.page_num[0]+=1

    # ===== P7-8: 仕事攻略 =====
    y=b.chapter_header('CHAPTER 4','仕事攻略マップ')
    b.c.setFont('HeiseiKakuGo-W5',FS['small']); b.c.setFillColorRGB(*col['muted'])
    b.c.drawString(MARGIN,y,'フィクサーが仕事で最も輝くのは「全体が見えていて、自分だけが知っている」状況です。'); y-=22
    y=b.section_heading('最も合う職種・役割（5選）',y)
    for jt,jd in td['work']:
        need=FS['heading']+(len(jd)//36+2)*LEADING+12
        y=b.check_page(y,need,tn,rank,legend_rate,'CHAPTER 4','仕事攻略')
        b.c.setFont('HeiseiKakuGo-W5',FS['heading']); b.c.setFillColorRGB(*col['accent'])
        b.c.drawString(MARGIN,y,jt); y-=FS['heading']+5
        y=b.draw_text(jd,MARGIN+8,y); y-=10
    y=b.check_page(y,160,tn,rank,legend_rate,'CHAPTER 4','仕事攻略')
    y=b.section_heading('上司・部下・同僚への接し方',y)
    for rt,rd in td['workRelations']:
        need=FS['body']+(len(rd)//36+2)*LEADING+10
        y=b.check_page(y,need,tn,rank,legend_rate,'CHAPTER 4','仕事攻略')
        b.c.setFont('HeiseiKakuGo-W5',FS['body']); b.c.setFillColorRGB(*col['accent'])
        b.c.drawString(MARGIN,y,rt); y-=LEADING
        y=b.draw_text(rd,MARGIN+8,y); y-=8
    y=b.check_page(y,180,tn,rank,legend_rate,'CHAPTER 4','仕事攻略')
    y=b.section_heading('キャリアアップのステップ',y)
    for ct,cd in td['career']:
        need=FS['heading']+(len(cd)//36+2)*LEADING+10
        y=b.check_page(y,need,tn,rank,legend_rate,'CHAPTER 4','仕事攻略')
        b.c.setFont('HeiseiKakuGo-W5',FS['heading']); b.c.setFillColorRGB(*col['accent'])
        b.c.drawString(MARGIN,y,ct); y-=FS['heading']+5
        y=b.draw_text(cd,MARGIN+8,y); y-=10
    b.footer(tn,rank,legend_rate); b.c.showPage(); b.page_num[0]+=1

    # ===== P9: お金攻略 =====
    y=b.chapter_header('CHAPTER 5','お金攻略戦略')
    b.c.setFont('HeiseiKakuGo-W5',FS['small']); b.c.setFillColorRGB(*col['muted'])
    b.c.drawString(MARGIN,y,'フィクサーとお金の関係は「見えにくい資産を作るのが得意」という一言に集約されます。'); y-=22
    for title,body in td['money']:
        lc=sum(len(p)//36+1 for p in body.split('\n'))
        need=FS['heading']+10+lc*LEADING+14
        y=b.check_page(y,need,tn,rank,legend_rate,'CHAPTER 5','お金攻略')
        y=b.section_heading(title,y); y=b.draw_text(body,MARGIN,y); y-=14
    b.footer(tn,rank,legend_rate); b.c.showPage(); b.page_num[0]+=1

    # ===== 最終P: LEGEND条件 =====
    y=b.chapter_header('FINAL','LEGENDへの最終条件')
    y=b.draw_text(td['legendCondition'],MARGIN,y); y-=16
    b.hline(y); y-=14
    final=f'LEGEND到達率{legend_rate}%のあなたへ：\n{tm["final"]}'
    lc=sum(len(p)//36+1 for p in final.split('\n'))
    bxH=lc*LEADING+28
    y=b.check_page(y,bxH+40,tn,rank,legend_rate)
    b.c.setFillColorRGB(0.12,0.10,0.04); b.c.setStrokeColorRGB(*col['accent']); b.c.setLineWidth(0.8)
    b.c.roundRect(MARGIN-4,y-bxH+14,W-MARGIN*2+8,bxH,4,fill=1,stroke=1)
    fy=y
    for para in final.split('\n'):
        for i in range(0,max(1,len(para)),36):
            b.c.setFont('HeiseiKakuGo-W5',FS['body']); b.c.setFillColorRGB(*col['text'])
            b.c.drawString(MARGIN+8,fy,para[i:i+36]); fy-=LEADING
    y-=bxH+12; b.hline(y); y-=14
    b.c.setFont('HeiseiKakuGo-W5',FS['small']); b.c.setFillColorRGB(*col['muted'])
    b.c.drawCentredString(W/2,y,'人生攻略ギルド　運命職業診断'); y-=14
    b.c.drawCentredString(W/2,y,f'{code} {td["name"]} / {rank}ランク / LEGEND{legend_rate}%')
    b.footer(tn,rank,legend_rate)

    return b.save()


# ===== Vercel Handler =====
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
            code       = body.get('code', 'FX')
            rank       = body.get('rank', 'A')
            legend_rate= int(body.get('legendRate', 88))
            norm       = body.get('norm', {})

            pdf_bytes = generate_pdf(code, rank, legend_rate, norm)

            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', f'attachment; filename="unmei_{code}_{rank}_{legend_rate}pct.pdf"')
            self.send_header('Content-Length', str(len(pdf_bytes)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(pdf_bytes)

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
