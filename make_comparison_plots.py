"""Three static comparison figures, reusing the established SVG/PNG renderer."""

import json
from project_paths import ROOT, RESULTS
from hydraulic_model import HydraulicModel
from make_visuals import Figure, HERE, NAVY, BLUE, TEAL, ORANGE, GRAY, GRID, RED


def legend(fig,x,y,color,label):
    fig.box(x,y+3,23,23,fill=color,stroke=color)
    fig.text(x+36,y,label,22)


def power_plot(r):
    fig = Figure(1500,960)
    fig.text(55,32,"Pumping electricity across the cooling loads",36,bold=True)
    fig.text(55,88,"Conceptual 1 MW loop · assumed 5 K water rise · same staging rule and required flow",22,GRAY)
    x0,y0,w,h = 150,190,1210,510
    bottom = y0+h
    for value in range(0,19,3):
        y=bottom-value/18*h
        fig.line([(x0,y),(x0+w,y)],GRID,1)
        fig.text(x0-20,y-10,str(value),21,anchor="end")
    fig.text(x0,y0-43,"Electrical input (kW)",23)
    fig.line([(x0,y0),(x0,bottom),(x0+w,bottom)],NAVY,2)
    for load,centre in zip([.4,.7,1.],[340,755,1170]):
        for strategy,offset,color in [("fixed",-79,ORANGE),("variable",32,TEAL)]:
            p=next(p for p in r["normal"] if p["strategy"]==strategy and p["load_fraction"]==load)
            height=p["electrical_power_kW"]/18*h
            fig.box(centre+offset,bottom-height,84,height,fill=color,stroke=color)
            fig.text(centre+offset+42,bottom-height-35,f"{p['electrical_power_kW']:.3f}",23,color,True,anchor="middle")
        fig.text(centre,bottom+22,f"{load:.0%} cooling load",24,bold=True,anchor="middle")
    legend(fig,250,785,ORANGE,"Fixed speed + throttling")
    legend(fig,800,785,TEAL,"Variable speed + pressure reset")
    fig.text(75,848,"Running pumps at 40/70/100% load: 1/2/2. Each pair of bars supplies the same required water flow.",23)
    fig.text(75,893,"VSD speeds: 66.67%, 67.78%, 96.82% of 1450 rpm. Full-load savings are small; partial-load valve losses matter.",22,GRAY)
    fig.save("comparison_power")


def heads_plot(a,r):
    fig=Figure(1700,1040)
    fig.text(55,32,"Where the pump head goes",36,bold=True)
    fig.text(55,88,"Stacked losses equal gross pump head; individual branch loss uses branch flow, shared losses use total flow",23,GRAY)
    model=HydraulicModel(a)
    x0,y0,w,h=120,195,1470,530
    bottom=y0+h
    for value in range(0,33,4):
        y=bottom-value/32*h
        fig.line([(x0,y),(x0+w,y)],GRID,1)
        fig.text(x0-18,y-10,str(value),21,anchor="end")
    fig.text(x0,y0-44,"Head (m water)",23)
    for load,centre in zip([.4,.7,1.],[370,870,1370]):
        for strategy,offset in [("fixed",-104),("variable",33)]:
            p=next(p for p in r["normal"] if p["strategy"]==strategy and p["load_fraction"]==load)
            Q=p["achieved_flow_m3_s"]
            components=[(model.R_upstream*Q*Q,GRAY),(model.R_coil*Q*Q,BLUE),
                        (p["valve_head_m"],ORANGE),(p["branch_loss_m"],TEAL)]
            y=bottom
            for value,color in components:
                height=value/32*h
                fig.box(centre+offset,y-height,88,height,fill=color,stroke="white")
                y-=height
            fig.text(centre+offset+44,y-35,f"{p['pump_head_m']:.2f}",23,bold=True,anchor="middle")
            fig.text(centre+offset+44,bottom+18,"Fixed" if strategy=="fixed" else "VSD",22,anchor="middle")
        fig.text(centre,bottom+63,f"{load:.0%} load",25,bold=True,anchor="middle")
    legend(fig,130,855,GRAY,"Shared pipes + plant HX")
    legend(fig,610,855,BLUE,"Equivalent coil bank")
    legend(fig,1110,855,ORANGE,"Control valve")
    legend(fig,130,902,TEAL,"Individual pump branch")
    fig.text(70,970,"At 40%, VSD still throttles: the speed-scaled upper flow limit prevents further slowing with one pump.",24,GRAY)
    fig.save("comparison_head_losses")


def sensitivity_plot(r):
    fig=Figure(1700,1110)
    fig.text(55,32,"How the assumptions change annual pumping energy",36,bold=True)
    fig.text(55,88,"Positive = less energy with variable speed; negative = more energy. Every annual profile totals 8760 h.",23,GRAY)
    rows=r["named_sensitivity"][:9]
    x0,x1,y0=650,1530,210
    mapx=lambda value:x0+(value+15)/80*(x1-x0)
    for tick in range(-10,66,10):
        x=mapx(tick)
        fig.line([(x,y0-35),(x,y0+len(rows)*72-25)],GRID,1)
        fig.text(x,y0+len(rows)*72,str(tick)+"%",21,anchor="middle")
    zero=mapx(0)
    fig.line([(zero,y0-35),(zero,y0+len(rows)*72-25)],NAVY,2)
    for index,row in enumerate(rows):
        y=y0+index*72
        value=row["savings_percent"]
        fig.text(65,y+3,row["name"],24)
        end=mapx(value)
        color=TEAL if value>=0 else RED
        fig.box(min(zero,end),y,abs(end-zero),35,fill=color,stroke=color)
        fig.text(end+12 if value>=0 else end-12,y+4,f"{value:+.1f}%",23,color,True,anchor="start" if value>=0 else "end")
    fig.text(65,945,"Combined unfavourable: +10% resistance, 8 m terminal floor, adverse efficiencies, 90% of hours at full load.",22)
    fig.text(65,990,"Capacity failures: +25% resistance or a 14 m terminal floor cannot meet full flow with two available pumps.",22,RED)
    fig.text(65,1035,"Annual comparisons require feasible duty at every load. The range describes the scenarios tested and carries no confidence level.",22,GRAY)
    fig.save("comparison_sensitivity")


if __name__=="__main__":
    a=json.loads((ROOT/"assumptions.json").read_text(encoding="utf-8"))
    r=json.loads((RESULTS/"comparison_results.json").read_text(encoding="utf-8"))
    power_plot(r); heads_plot(a,r); sensitivity_plot(r)
    print("Saved three comparison plots, each as PNG and SVG.")
