"""Create the three-page released case study from verified model results.

This concise report has deliberately fixed engineering labels. Its released
assumptions fingerprint prevents edited inputs producing stale explanatory text.
After changing the design basis, re-derive independent checks, review this text
and update RELEASED_INPUT_SHA256 only after that review. Data-only runs remain
available for edited assumptions.
"""

import hashlib
import json
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfgen import canvas
from project_paths import ROOT, RESULTS, REPORT
import visual_style as theme

RELEASED_INPUT_SHA256 = "dbc2cfd0e0b2979a9f220810d71aa113b1677fa3f917164162c2ae8dfb170543"
INK = colors.HexColor(theme.INK)
MUTED = colors.HexColor(theme.MUTED)
SAGE = colors.HexColor(theme.SAGE)
PLUM = colors.HexColor(theme.PLUM)
LINE = colors.HexColor(theme.LINE)
PALE = colors.HexColor(theme.PALE)
PAPER = colors.HexColor(theme.PAPER)
RED = colors.HexColor(theme.RED)
PAGE_W, PAGE_H = A4
MARGIN = 42
WIDTH = PAGE_W - 2*MARGIN


class Report:
    def __init__(self,path):
        theme.register_pdf_fonts()
        self.c = canvas.Canvas(str(path),pagesize=A4,invariant=1,initialFontName="Calibri")
        self.c.setTitle("Data centre chilled-water pumping and N+1 capacity")
        self.c.setAuthor("Independent engineering portfolio project")
        self.c.setSubject("Conceptual simulation: equal-flow pumping comparison and steady-state N+1 capacity")
        self.min_bottom = []

    def para(self,text,y,size=10,leading=13,width=WIDTH,x=MARGIN,color=INK,space=6):
        style=ParagraphStyle("body",fontName="Calibri",fontSize=size,leading=leading,
                             textColor=color,alignment=TA_LEFT,spaceAfter=0)
        p=Paragraph(text,style)
        _,height=p.wrap(width,1000)
        p.drawOn(self.c,x,y-height)
        return y-height-space

    def heading(self,title,y):
        self.c.setFillColor(PLUM); self.c.setFont("Calibri-Bold",11)
        self.c.drawString(MARGIN,y-11,title)
        return y-23

    def title(self,title,subtitle,page):
        c=self.c
        c.setFillColor(PAPER);c.rect(0,0,PAGE_W,PAGE_H,stroke=0,fill=1)
        c.setFillColor(PLUM);c.rect(0,PAGE_H-112,6,112,stroke=0,fill=1)
        c.setFont("Calibri",9);c.setFillColor(MUTED)
        c.drawString(MARGIN,PAGE_H-34,"Independent engineering project")
        c.setFont("Calibri-Bold",9);c.setFillColor(SAGE)
        chapter=["Design","Results","Judgement"][page-1]
        c.drawRightString(PAGE_W-MARGIN,PAGE_H-34,f"0{page} / {chapter}")
        c.setFillColor(INK);c.setFont("Calibri-Bold",26)
        c.drawString(MARGIN,PAGE_H-68,title)
        c.setFillColor(MUTED);c.setFont("Calibri",10.5)
        c.drawString(MARGIN,PAGE_H-89,subtitle)
        c.setStrokeColor(LINE);c.setLineWidth(.7)
        c.line(MARGIN,PAGE_H-106,PAGE_W-MARGIN,PAGE_H-106)
        c.line(MARGIN,38,PAGE_W-MARGIN,38)
        c.setFillColor(MUTED);c.setFont("Calibri",8)
        c.drawString(MARGIN,24,"Chilled-water pumping / 1 MW concept")
        c.setFont("Calibri-Bold",8)
        c.drawRightString(PAGE_W-MARGIN,24,f"0{page} / 03")
        return PAGE_H-120

    def table(self,data,widths,y,size=9):
        style=ParagraphStyle("cell",fontName="Calibri",fontSize=size,leading=size+2,textColor=INK)
        header=ParagraphStyle("header",parent=style,fontName="Calibri-Bold",textColor=colors.white)
        cells=[[Paragraph(str(value),header if i==0 else style) for value in row] for i,row in enumerate(data)]
        t=Table(cells,colWidths=widths,hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONTNAME",(0,0),(-1,-1),"Calibri"),
            ("BACKGROUND",(0,0),(-1,0),PLUM),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,PALE]),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
            ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
            ("LINEBELOW",(0,0),(-1,0),.7,LINE),("LINEBELOW",(0,1),(-1,-1),.35,LINE)]))
        _,height=t.wrap(WIDTH,1000);t.drawOn(self.c,MARGIN,y-height)
        return y-height-7

    def end(self,y):
        self.min_bottom.append(y)
        if y<46:
            raise ValueError(f"Page content overruns footer: bottom={y}")
        self.c.showPage()


def schematic(r,y):
    c=r.c;x=MARGIN
    c.setFillColor(PALE);c.roundRect(x,y-153,WIDTH,153,6,stroke=0,fill=1)
    c.saveState();c.translate(x+4,y-143)
    c.setStrokeColor(SAGE);c.setLineWidth(1.25)
    def line(points):
        p=c.beginPath();p.moveTo(*points[0])
        for pt in points[1:]:p.lineTo(*pt)
        c.drawPath(p)
    def label(cx,cy,text,size=8,bold=False,color=INK):
        c.setFillColor(color);c.setFont("Calibri-Bold" if bold else "Calibri",size);c.drawCentredString(cx,cy,text)
    def box(cx,cy,w,h,labeltext):
        c.setFillColor(colors.white);c.setStrokeColor(SAGE);c.rect(cx-w/2,cy-h/2,w,h,fill=1,stroke=1)
        label(cx,cy-3,labeltext,8,True)
    def arrow(x1,y1,x2,y2):
        line([(x1,y1),(x2,y2)])
        dx,dy=x2-x1,y2-y1
        length=(dx*dx+dy*dy)**.5;ux,uy=dx/length,dy/length
        p=c.beginPath();p.moveTo(x2,y2)
        p.lineTo(x2-4*ux+2*uy,y2-4*uy-2*ux)
        p.lineTo(x2-4*ux-2*uy,y2-4*uy+2*ux);p.close()
        c.setFillColor(SAGE);c.drawPath(p,fill=1,stroke=0)
    line([(14,32),(14,90)]);line([(204,32),(204,90)])
    for i,yy in enumerate([90,61,32]):
        if i==2:c.setDash(3,2)
        line([(14,yy),(204,yy)])
        for cx,w,txt in [(40,22,"IV"),(83,32,f"P{i+1}"),(128,26,"CV"),(173,22,"IV")]:box(cx,yy,w,16,txt)
        c.setDash()
    label(109,113,"2 duty + 1 standby",8.5,True)
    label(109,7,"Each branch: 2 m at 86.03 m3/h",7.5)
    line([(204,61),(220,61),(220,113),(240,113)])
    line([(316,113),(342,113)]);line([(420,113),(445,113)])
    line([(491,113),(499,113),(499,-1),(14,-1),(14,32)])
    box(278,113,76,28,"Plant HX")
    box(381,113,78,28,"CRAH coils")
    box(468,113,46,28,"Valve")
    c.setStrokeColor(SAGE)
    arrow(318,113,338,113);arrow(423,113,441,113)
    arrow(357,-1,334,-1);arrow(499,54,499,34)
    label(278,89,"4 m",7.6);label(381,89,"8 m",7.6);label(468,89,"2 m open",7.6)
    label(329,135,"Supply 12.5 C",7.7,color=SAGE)
    label(417,16,"Return 17.5 C",7.7,color=PLUM)
    label(330,33,"Shared pipe/header loss: 6 m",8)
    c.setStrokeColor(MUTED);c.setLineWidth(.7)
    line([(341,79),(341,69),(493,69),(493,79)])
    label(417,56,"Remote DP: coil + valve",7.7)
    label(4,58,"S",8,True);label(212,48,"D",8,True)
    c.restoreState()
    return y-160


def small_plot(r,x,top,w,h,title,rows,field,unit):
    c=r.c
    c.setFillColor(INK);c.setFont("Calibri-Bold",10);c.drawString(x,top,title)
    left,bottom=x+27,top-h+25
    chart_w,chart_h=w-38,h-51
    ymax=18 if field=="electrical_power_kW" else 24
    c.setFont("Calibri",8);c.setFillColor(MUTED);c.drawString(x,top-14,unit)
    for tick in [0,ymax/3,2*ymax/3,ymax]:
        yy=bottom+tick/ymax*chart_h
        c.setStrokeColor(LINE);c.setLineWidth(.4);c.line(left,yy,left+chart_w,yy)
        c.setFillColor(MUTED);c.drawRightString(left-5,yy-2,f"{tick:g}")
    for load,idx in zip([.4,.7,1.],range(3)):
        centre=left+chart_w*(idx+.5)/3
        for strategy,off,col in [("fixed",-17,PLUM),("variable",3,SAGE)]:
            p=next(p for p in rows if p["strategy"]==strategy and p["load_fraction"]==load)
            value=p[field];height=value/ymax*chart_h
            c.setFillColor(col);c.rect(centre+off,bottom,15,height,stroke=0,fill=1)
            c.setFont("Calibri",8);c.drawCentredString(centre+off+7.5,bottom+height+5,f"{value:.1f}")
        c.setFillColor(INK);c.setFont("Calibri",8);c.drawCentredString(centre,bottom-14,f"{load:.0%}")
    c.setFillColor(PLUM);c.rect(x+31,top-h+2,8,8,stroke=0,fill=1)
    c.setFillColor(INK);c.setFont("Calibri",8);c.drawString(x+43,top-h+2,"Fixed")
    c.setFillColor(SAGE);c.rect(x+103,top-h+2,8,8,stroke=0,fill=1)
    c.setFillColor(INK);c.drawString(x+115,top-h+2,"Variable")


def main():
    raw=(ROOT/"assumptions.json").read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=RELEASED_INPUT_SHA256:
        raise ValueError("Changed report basis: review fixed method labels/checks before updating RELEASED_INPUT_SHA256")
    a=json.loads(raw);data=json.loads((RESULTS/"comparison_results.json").read_text())
    baseline=json.loads((RESULTS/"baseline_results.json").read_text())
    checks=json.loads((RESULTS/"comparison_verification.json").read_text())
    if data["assumptions_sha256"]!=digest or baseline["assumptions_sha256"]!=digest or not checks["all_passed"]:
        raise ValueError("Report requires current, verified outputs")
    rows=data["normal"];energy=data["annual_energy_profiles"]["reference"]
    out=REPORT/"chilled_water_pumping_case_study.pdf"
    r=Report(out)

    y=r.title("Chilled-water pumping","A 1 MW data hall: energy use and steady-state N+1 capacity",1)
    y=r.heading("The engineering question",y)
    y=r.para("How much pumping electricity could variable speed save as a data hall's cooling load changes? Could the loop still supply the required water flow with one pump unavailable? I explored both questions in a conceptual Python model at 40%, 70% and 100% load. An adequately sized external plant maintains the chilled-water supply temperature.",y)
    y=schematic(r,y-1)
    y=r.para("The boundary follows the closed secondary water loop. IV = isolation valve; CV = discharge check valve; HX = heat exchanger; CRAH = computer room air handler. S and D are the pump suction and discharge headers. Head budgets are illustrative. A closed expansion/fill connection at S sits outside the flow model.",y,size=8.6,leading=11)
    y=r.heading("Design basis",y)
    design=[
      ["Input and evidence", "Value used"],
      ["Heat demand / assumed", "1 MW at full load; supply/return 12.5/17.5 C. A constant 5 K rise gives 47.75 kg/s, or 172.05 m<super>3</super>/h, at full duty."],
      ["Water / sourced [1,2]", "At 15 C: density 999.1 kg/m<super>3</super>; specific heat 4188.55 J/(kg K); viscosity 1.138 x 10<super>-3</super> Pa s. Properties held constant."],
      ["Pumps / illustrative", "Three identical parallel pumps: two duty and one standby. Each reference point is 86.03 m<super>3</super>/h at 24 m head and 1450 rpm; curves represent assumed hardware."],
      ["Losses / assumed", "At total reference flow: pipes/headers 6 m, plant HX 4 m, coils 8 m, fully-open valve 2 m. Each pump branch loses 2 m at its own reference flow."]]
    y=r.table(design,[126,WIDTH-126],y)
    y=r.heading("How the comparison works",y)
    y=r.para("Required mass flow = heat/(cp x DeltaT); volume flow Q = mass flow/density. Hardware reference flows stay fixed when demand changes. With u = Q/Qref, y = q/qBEP = 2u/n, speed fraction s = rpm/1450 and n running pumps:",y)
    y=r.para("<b>Gross pump head = 32s<super>2</super> - 8y<super>2</super> m; branch loss = 2y<super>2</super> m.</b> Subtracting branch loss gives the header head, which intersects the shared system curve, 18u<super>2</super> + valve loss. Parallel flows add at a common header pressure [4]. Elevation cancels around the filled closed loop [3].",y)
    y=r.para("Both strategies stage the fewest feasible pumps: 1/2/2 across the three loads. Fixed speed uses valve throttling at s = 1. Variable speed resets remote differential pressure (DP): minimum header head = 10u<super>2</super> + max(10u<super>2</super>, 2) m. The 2 m floor applies across coil plus valve. Speed/flow limits can require extra head, absorbed by the same valve [5,6].",y)
    y=r.para("<b>Assumed operating limits:</b> s = 0.5-1.0; branch flow = 0.45-1.20 of speed-scaled best-efficiency-point (BEP) flow; valve rangeability 25:1, differential at most 30 m; motor shaft rating 11 kW each. Pump efficiency = 0.80 - 0.35(y/s - 1)<super>2</super>; motor 0.93; variable-frequency drive (VFD) 0.97, fixed drive factor 1.",y,size=9.1,leading=11.6)
    r.end(y)

    y=r.title("What the model found","Equal water flow at each load, with lower head where the controls allow it",2)
    y=r.para("Each pair below delivers the same heat-balance flow and meets the same terminal pressure requirement. The imposed 5 K water rise keeps demand comparable; actual coil behaviour would need separate assessment. Healthy pumps also reproduce these final operating points after any one pump is removed.",y)
    table=[["Load","Strategy","Flow<br/>m<super>3</super>/h","Pumps","Speed<br/>rpm","Gross<br/>head m","Valve<br/>loss m","Input<br/>kW"]]
    for load in [.4,.7,1.]:
        for strategy in ["fixed","variable"]:
            p=next(p for p in rows if p["load_fraction"]==load and p["strategy"]==strategy)
            table.append([f"{load:.0%}",strategy.title(),f"{p['achieved_flow_m3_h']:.2f}",str(p['running_pumps']),f"{p['speed_rpm']:.0f}",f"{p['pump_head_m']:.2f}",f"{p['valve_head_m']:.2f}",f"{p['electrical_power_kW']:.3f}"])
    y=r.table(table,[34,58,66,40,61,75,75,WIDTH-409],y)
    plot_top=y-3;plot_h=160;gap=20;plot_w=(WIDTH-gap)/2
    small_plot(r,MARGIN,plot_top,plot_w,plot_h,"Electrical pumping input",rows,"electrical_power_kW","kW")
    small_plot(r,MARGIN+plot_w+gap,plot_top,plot_w,plot_h,"Control-valve head loss",rows,"valve_head_m","m water")
    y=plot_top-plot_h-11
    y=r.heading("One pump unavailable",y)
    y=r.para("<b>All 18 outage cases meet required flow within the declared limits.</b> At 40% load, P1 runs, P2 is staged off and P3 is standby. At 70/100%, P1 and P2 run. Losing P3 removes the spare; losing P1 calls for P3 to replace it. These results describe steady-state N+1 pumping capacity after substitution. The changeover itself lies outside the model.",y)
    y=r.heading("Why some throttling remains",y)
    y=r.para("At 40%, one pump reaches its upper speed-scaled flow limit, setting s = 0.8/1.2 = 0.667. Slowing further would leave the assumed operating envelope, so the valve still absorbs 4.94 m. At 70/100%, it is fully open and retains its physical loss. Full-load savings fall to 5.45%. Two slow pumps at 40% use 1.776 kW in a separate staging check, versus 2.405 kW with one; that alternative is excluded from annual totals.",y)
    y=r.heading("Checks and annual pumping energy",y)
    y=r.para("The model passes <b>33 engineering checks</b> (16 baseline, 17 comparison), including an independent audit of 128 feasible comparison records. Checks cover heat balance, units, branch continuity, curve intersections, power and operating limits. At 70% load, a separate calculation gives P = 999.1 x 9.81 x 0.0334546 x 10.78/(0.799624 x 0.93 x 0.97) = <b>4.900 kW</b> [5].",y)
    y=r.para(f"An illustrative year assigns 3504/3504/1752 hours to 40/70/100% load, totalling 8760 h. Multiplying each calculated input by its hours gives <b>{energy['fixed_kWh']/1000:.2f} MWh fixed</b> and <b>{energy['variable_kWh']/1000:.2f} MWh variable</b>: a <b>{energy['savings_kWh']/1000:.2f} MWh/year ({energy['savings_percent']:.1f}%) modelled pumping-energy reduction</b>. Power uses actual head, flow and efficiency at every point.",y)
    r.end(y)

    y=r.title("Engineering judgement","Pressure, equipment performance and operating hours shape the answer",3)
    y=r.heading("Recommendation",y)
    y=r.para("Variable-speed pumping with commissioned pressure reset is worth taking forward for the reference partial-load profile. Before choosing equipment, I would obtain pump/drive maps, establish the critical-path pressure requirement and check the site's load hours. The sensitivity results show how readily those choices can change the answer.",y)
    y=r.heading("What changes the energy result?",y)
    sens=[["Change from the reference case", "Annual saving"]]
    for name in ["Reference","Resistance -20%","Resistance +10%","Terminal minimum 8 m","Terminal minimum 12 m","Adverse efficiencies","More partial-load hours","More full-load hours","Combined unfavourable"]:
        item=next(p for p in data["named_sensitivity"] if p["name"]==name)
        sens.append([name,f"{item['savings_percent']:+.1f}%"])
    y=r.table(sens,[WIDTH-104,104],y,size=9)
    y=r.para("Resistance scales shared passive and branch losses; valve hardware stays fixed. Adverse efficiencies: pump peak 0.72, curve coefficient 0.50, motor 0.90, VFD 0.90. Partial/full-load-heavy profiles use 6132/1752/876 and 438/438/7884 hours. The combined case pairs +10% resistance and an 8 m floor with adverse efficiencies and full-load-heavy hours, using 6.96% more energy.",y,size=9,leading=11.6)
    env=data["sensitivity_envelope"]
    y=r.para(f"Of 54 tested combinations, {env['cases_comparable']} permit an annual comparison and {env['cases_infeasible']} fail a required duty. Feasible savings range from <b>{env['min_savings_percent']:.1f}% to +{env['max_savings_percent']:.1f}%</b>, with 44/48 saving energy. This range describes the chosen scenarios; it carries no statistical confidence level. Infeasible duties receive no annual savings estimate.",y)
    y=r.para("<b>Capacity margin deserves attention.</b> With +25% passive/branch resistance, two pumps deliver 164.51 m<super>3</super>/h against 172.05 required. A 14 m terminal floor also fails full duty. At the reference floor, +10% resistance uses up the full-load speed/head margin.",y,color=RED)
    y=r.heading("What still needs evidence",y)
    y=r.para("Pump curves, efficiencies and loss budgets are illustrative; the CRAH terminals form one balanced load. <b>Coil heat-transfer performance, rack inlet temperatures and transient cooling continuity remain unverified.</b> Fill pressure, net positive suction head (NPSH) and valve suitability need checking. Ride-through requires pump startup/flow timing, thermal inventory and mixing, coil/fan behaviour, IT heat load and temperature limits.",y)
    y=r.para("The energy boundary covers secondary pumps. Refrigeration, CRAH fans and heat rejection would be needed for total cooling energy or PUE. Equipment selection and site or AWS design approval lie beyond this independent study. Practical pressure reset needs critical-path DP sensing, valve-position feedback and commissioned control limits [5,6].",y,size=9,leading=11.6)
    y=r.heading("References and reproducibility",y)
    references=[
        ("[1] ITTC 7.5-02-01-03, rev.02, Table 1 p.6: water density and viscosity.","https://www.ittc.info/media/7989/75-02-01-03.pdf"),
        ("[2] IAPWS SR6-08(2011), Tables 1-2 and 8: heat capacity and checkpoints.","https://iapws.org/technical-guidance/release/LiquidWater.download"),
        ("[3] Bell & Gossett TEH-471A, p.2: closed-loop operating head.","https://prod.xylem.com/siteassets/brand/bell-amp-gossett/resources/manual/teh-471a-hydronic-system-types.pdf"),
        ("[4] KSB, Parallel operation: common-head flow addition and check valves.","https://www.ksb.com/en-global/centrifugal-pump-lexicon/article/parallel-operation-1116902"),
        ("[5] ASHRAE Handbook 2020, ch.44, sections 13-15: pressure control/efficiency.","https://handbook.ashrae.org/Handbooks/S20/IP/s20_ch44/s20_ch44_ip.aspx"),
        ("[6] ASHRAE Handbook 2023, ch.43, Optimal DP Set Points: terminal-based reset.","https://handbook.ashrae.org/Handbooks/A23/SI/a23_ch43/a23_ch43_si.aspx")]
    for label,url in references:
        y=r.para(f'<link href="{url}" color="#68455F">{label}</link>',y,size=8.1,leading=10,space=2)
    y=r.para("References support the methods and water properties. Run <b>python run_project.py</b> to regenerate the packaged results and report. The final code review fixed hardware reference flows; the published 5 K results were unchanged.",y,size=8.3,leading=10.5)
    r.end(y)
    r.c.save()
    print("Saved",out.name,"(3 pages, embedded Calibri); content bottoms:",[round(v,1) for v in r.min_bottom])


if __name__=="__main__":
    main()
