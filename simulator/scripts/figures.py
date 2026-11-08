"""Every figure has a matching numerical table. All plots are research artifacts."""
from pathlib import Path
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from belleq_sim.common import ROOT, METHODS, SEED, csv_read, csv_write, write_json, event, empirical_ci
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
import numpy as np
from belleq_sim.engine import simulate,load_artifacts

LABELS={'semantic_sequential':'Semantic sequential','broadcast':'Parallel broadcast',
        'random_sequential':'Random sequential','single_db':'Single database'}
COLORS=['#0072B2','#009E73','#D55E00','#CC79A7']
LINE_STYLES={
    'semantic_sequential':dict(color=COLORS[0],marker='*',markersize=11),
    'broadcast':dict(color=COLORS[1],marker='s',markersize=7),
    'random_sequential':dict(color=COLORS[2],marker='^',markersize=7),
}
THRESHOLD_GRID=[i/10 for i in range(11)]

def save(fig,name,caption):
    out=ROOT/'figures';out.mkdir(exist_ok=True)
    fig.savefig(out/(name+'.png'),dpi=220,bbox_inches='tight')
    fig.savefig(out/(name+'.pdf'),bbox_inches='tight')
    (out/(name+'.caption.txt')).write_text(caption+'\n')
    plt.close(fig)

def draw_scaling(grid):
    fig,axs=plt.subplots(1,2,figsize=(12,4.6))
    for m in METHODS[:3]:
        rr=[r for r in grid if r['method']==m]
        for ax,key,scale,label in zip(axs,['mean_ms','mean_frame_bytes'],[1,1000],
                    ['Mean retrieval latency (ms)','Mean estimated frame traffic (kB/query)']):
            ax.plot([int(r['nodes']) for r in rr],[float(r[key])/scale for r in rr],
                    linestyle='--',label=LABELS[m],markerfacecolor='none',
                    markeredgewidth=1.3,linewidth=1.5,**LINE_STYLES[m])
            ax.set_xlabel('Virtual search workers (coordinator excluded)');ax.set_ylabel(label)
    for ax in axs:
        ax.relim();ax.autoscale(enable=True,axis='y');ax.set_ylim(bottom=0)
    axs[0].legend(fontsize=8);fig.suptitle('Assumption scenarios only — worker-count scaling has NOT been validated')
    fig.tight_layout()
    save(fig,'03_scaling_assumptions','Every curve is a hypothetical simulation, not a measured scaling result. Reused per-worker cost/payload archetypes; no corpus-size model, queueing, or shared-link saturation. Semantic owner-first probability=.57 chosen as an assumption. New node counts do not predict retrieval quality. Consistent markers: semantic blue star, broadcast green square, random orange triangle.')

def compute_thresholds(artifacts):
    thresholds=[]
    for threshold in THRESHOLD_GRID:
        for m in METHODS[:3]:
            r=simulate(dict(mode='trace',method=m,nodes=3,threshold=threshold,draws=5000,seed=SEED),artifacts)
            thresholds.append(dict(threshold=threshold,method=m,reference_hit_rate=r['reference_hit_rate'],
                mean_visits=r['summary']['visited_nodes']['mean'],mean_body_bytes=r['summary']['application_body_bytes']['mean']))
    csv_write(ROOT/'results/threshold_trace_replay.csv',thresholds)
    return thresholds

def draw_thresholds(thresholds):
    fig,axs=plt.subplots(1,2,figsize=(12,4.3))
    for m in METHODS[:3]:
        rr=[r for r in thresholds if r['method']==m]
        for ax,key,scale in zip(axs,['reference_hit_rate','mean_visits'],[100,1]):
            ax.plot([float(r['threshold']) for r in rr],[scale*float(r[key]) for r in rr],
                    linestyle='-',label=LABELS[m],markerfacecolor='none',
                    markeredgewidth=1.3,linewidth=1.5,**LINE_STYLES[m])
    axs[0].set_ylabel('Reference passage hit (%)');axs[0].set_ylim(-3,100)
    axs[0].set_yticks([0,20,40,60,80,100])
    axs[1].set_ylabel('Mean workers visited');axs[1].set_ylim(0,3.2)
    for ax in axs:
        ax.set_xlabel('Minimum similarity score');ax.set_xticks(THRESHOLD_GRID)
        ax.set_xticklabels([f'{t:.1f}' for t in THRESHOLD_GRID]);ax.set_xlim(-.02,1.02)
    axs[0].legend(fontsize=8);fig.suptitle('Counterfactual threshold replay from recorded five-candidate lists')
    fig.tight_layout()
    save(fig,'04_threshold_replay','400 calibration questions only, resampled 5000 times per threshold from 0.0 to 1.0 in steps of 0.1. Candidate-list replay, not new vector searches or generated answers. Reference labels are synthetic and nonexhaustive; these rates are not answer accuracy. Consistent markers: semantic blue star, broadcast green square, random orange triangle.')

def update_line_figures():
    """Refresh only the two requested line charts; retain all other figures/data."""
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.grid':True,'grid.alpha':.18,'figure.dpi':110})
    draw_scaling(csv_read(ROOT/'results/scaling_assumptions.csv'))
    draw_thresholds(compute_thresholds(load_artifacts()))
    write_json(ROOT/'figures/line_series_encoding.json',LINE_STYLES)
    event('line_figures_updated',figures=['03_scaling_assumptions','04_threshold_replay'],
          threshold_grid=THRESHOLD_GRID,markers=LINE_STYLES,new_physical_experiments=False)
    print('Updated both line figures in PNG/PDF; replay thresholds 0.0..1.0 by 0.1.')

def main():
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.grid':True,'grid.alpha':.18,'figure.dpi':110})
    observed=json.loads((ROOT/'results/observed_summary.json').read_text())
    rows=csv_read(ROOT/'data/processed/observations.csv')
    table=[];fig,axs=plt.subplots(1,2,figsize=(12,4.5))
    for ax,target,scale,label in zip(axs,['aggregate_ms','network_frame_bytes'],[1,1000],
            ['Retrieval latency (ms)','Captured frame traffic (kB/query)']):
        means=[];intervals=[]
        for m in METHODS:
            rr=[r for r in rows if r['experiment_method']==m and (r['complete']=='True' or target=='network_frame_bytes')]
            values=[float(r[target]) for r in rr];ci=empirical_ci(values);mean=float(np.mean(values))
            table.append(dict(method=m,target=target,n=len(values),mean=mean,ci_low=ci[0],ci_high=ci[1]))
            means.append(mean/scale);intervals.append([(mean-ci[0])/scale,(ci[1]-mean)/scale])
        ax.bar(range(4),means,color=COLORS,yerr=np.array(intervals).T,capsize=4)
        ax.set_xticks(range(4),['Semantic\nsequential','Parallel\nbroadcast','Random\nsequential','Single\nDB'])
        ax.set_ylabel(label);ax.set_ylim(bottom=0)
    fig.suptitle('Observed trade-off: sequential routing reduces traffic but increases latency')
    fig.tight_layout()
    save(fig,'01_observed_tradeoff','Real .70 observations; 500 questions/method. Retrieval excludes generation. Traffic uses all attempts; latency uses complete requests. Error bars: question-bootstrap 95% CI of mean, not between-session uncertainty.')
    csv_write(ROOT/'results/figure01_data.csv',table)

    val=csv_read(ROOT/'results/monte_carlo_validation.csv')
    fig,axs=plt.subplots(1,2,figsize=(12,4.5))
    for ax,target,label,scale in zip(axs,['aggregate_ms','network_frame_bytes'],['Mean retrieval latency (ms)','Mean captured traffic (kB/query)'],[1,1000]):
        rr=[next(r for r in val if r['method']==m and r['target']==target) for m in METHODS]
        x=np.arange(4)
        ax.bar(x-.18,[float(r['test_mean'])/scale for r in rr],.36,label='Held-out real questions',color='#555555')
        ax.bar(x+.18,[float(r['simulated_mean'])/scale for r in rr],.36,label='Monte Carlo calibration',color='#56B4E9')
        ax.set_xticks(x,['Semantic','Parallel','Random','Single DB']);ax.set_ylabel(label);ax.set_ylim(bottom=0)
    axs[0].legend(fontsize=8);fig.suptitle('Native configurations: prediction checked on 100 unseen questions')
    fig.tight_layout()
    save(fig,'02_heldout_validation','400 calibration questions, 100 held-out questions, each with four method observations. 10000 Monte Carlo draws per method. Distribution-level validation in the original sessions only; not validation at new worker counts.')

    a=load_artifacts();grid=[]
    for n in [1,2,3,4,6,8,12,16]:
        for m in METHODS[:3]:
            cfg=dict(mode='assumption',method=m,nodes=n,draws=3000,seed=SEED,
                     semantic_owner_first_probability=.57 if m=='semantic_sequential' else None)
            r=simulate(cfg,a)
            grid.append(dict(nodes=n,method=m,mean_ms=r['summary']['retrieval_ms']['mean'],
                p95_ms=r['summary']['retrieval_ms']['p95'],mean_frame_bytes=r['summary']['network_frame_bytes']['mean'],
                mean_visits=r['summary']['visited_nodes']['mean'],draws=3000,
                evidence='unvalidated assumptions; one owner and N-1 virtual distractor archetypes; owner-first=.57'))
    csv_write(ROOT/'results/scaling_assumptions.csv',grid)
    draw_scaling(grid)
    draw_thresholds(compute_thresholds(a))
    write_json(ROOT/'figures/line_series_encoding.json',LINE_STYLES)

    # Model report makes the unsuccessful regression comparisons visible.
    reports=json.loads((ROOT/'results/model_validation.json').read_text())
    fig,axs=plt.subplots(1,3,figsize=(12,3.8))
    for ax,target,label in zip(axs,['aggregate_ms','network_frame_bytes','client_ms'],['Retrieval MAE (ms)','Traffic MAE (bytes)','End-to-end MAE (ms)']):
        r=reports[target]
        ax.bar(['Method mean','Ridge'],[r['frozen_test_baseline']['mae'],r['frozen_test_ridge']['mae']],color=['#999999','#0072B2'])
        ax.set_ylabel(label);ax.set_ylim(bottom=0)
    fig.suptitle('Frozen test: simple regression does not beat the baseline for every output')
    fig.tight_layout()
    save(fig,'05_regression_baselines','100 held-out questions x four methods (400 complete observations). Selection and Ridge alpha search used validation questions only. All candidate metrics retained, including weak and negative results. Global R2 mixes between-method and within-method variation; consult per-method results.')
    event('06_figures_created',figures=5,formats=['png','pdf'],tables_saved=True,
          scaling_validated=False,bootstrap_ci_note='Question sampling uncertainty only, not session or extrapolation uncertainty')
    print('Saved five figures in PNG/PDF with captions and source tables.')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--line-only',action='store_true',help='Update only line figures and their replay table')
    args=parser.parse_args()
    update_line_figures() if args.line_only else main()
