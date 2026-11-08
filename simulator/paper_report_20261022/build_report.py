"""Build the paper report from immutable measured results and saved figures.

Run with the bundled document Python runtime. This script does not retrain models
or rerun experiments. All newly extracted tables retain their source case IDs.
"""
from pathlib import Path
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from statistics import mean

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
USED = set()

def source(rel):
    USED.add(rel)
    return ROOT / rel

def js(rel):
    return json.loads(source(rel).read_text())

def csvread(rel):
    with source(rel).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def csvwrite(name, rows):
    with (OUT/'tables'/name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)

for folder in ['tables', 'figures', 'qa']:
    (OUT/folder).mkdir(exist_ok=True)

observations = csvread('data/processed/observations.csv')
observed = js('results/observed_summary.json')
validation = csvread('results/monte_carlo_validation.csv')
regression = js('results/model_validation.json')
thresholds = csvread('results/threshold_trace_replay.csv')
scaling = csvread('results/scaling_assumptions.csv')
corpus = js('data/raw/oct12/corpus.json')
auxiliary = js('results/threshold_080_auxiliary.json')
audit = js('results/data_audit.json')
pcap = js('results/pcap_audit.json')
refs = js('references/sources.json')
for rel in ['research/METHODS_TR.md', 'research/RESULTS_TR.md',
            'research/DECISIONS_TR.md', 'research/journal.jsonl',
            'data/source_manifest.json', 'data/raw/oct12/run_manifest.json',
            'data/raw/oct14/consolidation.json', 'artifacts/model_card.json',
            'data/raw/service_snapshot/belleq_lab/config.py',
            'data/raw/service_snapshot/belleq_lab/routing.py',
            'scripts/figures.py', 'results/verification.json']:
    source(rel)
shutil.copy2(source('figures/line_series_encoding.json'),OUT/'figures/line_series_encoding.json')

METHODS = ['semantic_sequential', 'broadcast', 'random_sequential', 'single_db']
LABELS = dict(zip(METHODS, ['Semantic sequential', 'Parallel broadcast', 'Random sequential', 'Single database']))
by_case = defaultdict(list)
for r in observations:
    by_case[r['case_id']].append(r)

main_rows = []
for x in observed:
    rr = [r for r in observations if r['experiment_method']==x['method'] and r['complete']=='True']
    main_rows.append(dict(method=x['method'], attempted=x['n'], complete=x['complete'],
        mean_visits_complete=mean(float(r['visited_node_count']) for r in rr),
        retrieval_mean_ms=x['aggregate_ms']['mean'], retrieval_p95_ms=x['aggregate_ms']['p95'],
        frame_bytes_mean_all_attempts=x['network_frame_bytes']['mean'],
        client_mean_ms=x['client_ms']['mean'], hits=x['hits'],
        reference_hit_rate_all_attempts=x['hits']/x['n'],
        router_mean_ms_complete=mean(float(r['router_ms']) for r in rr),
        generation_invoked=x['generation_invoked']))
csvwrite('observed_comparison.csv', main_rows)
csvwrite('monte_carlo_validation.csv', validation)
csvwrite('threshold_trace_replay.csv', thresholds)
csvwrite('scaling_assumptions.csv', scaling)
csvwrite('corpus.csv', corpus)
csvwrite('figure01_data.csv', csvread('results/figure01_data.csv'))
(OUT/'tables'/'model_validation.json').write_text(json.dumps(regression,indent=2))
transport = []
for m in METHODS:
    rr = [r for r in observations if r['experiment_method']==m and r['complete']=='True']
    transport.append(dict(method=m, complete_n=len(rr),
        mean_of_query_mean_ack_rtt_ms=mean(float(r['mini1_network_ack_rtt_ms_mean']) for r in rr),
        mean_of_query_mean_http_response_ms=mean(float(r['mini1_network_http_response_ms_mean']) for r in rr),
        mean_of_query_tx_plus_rx_mbps=mean(float(r['mini1_network_tx_mbps'])+float(r['mini1_network_rx_mbps']) for r in rr),
        sum_recorded_retransmission_frames=sum(float(r['mini1_network_retransmission_frames']) for r in rr)))
csvwrite('coordinator_transport_summary.csv', transport)
failure_fields = ['case_id','experiment_method','http_status','error','network_frame_bytes','raw_response_json']
csvwrite('failure_records.csv', [{k:r[k] for k in failure_fields} for r in observations if r['complete']!='True'])

example_ids = ['pg35-027', 'pg244-008', 'pg2852-015']
example_fields = ['case_id','experiment_method','placement','question','answer','expected_answer',
    'book_title','evidence_quote','hit_at_k','complete','http_status','visited_nodes_json',
    'visited_node_count','aggregate_ms','router_ms','generation_ms','client_ms',
    'network_frame_bytes','body_bytes','split','quality_status']
example_fields += [k for k in observations[0] if k.startswith(('mini2_','mini3_','mini4_'))]
examples = [{k:r[k] for k in example_fields} for c in example_ids for r in by_case[c]]
csvwrite('example_query_rows.csv', examples)
schema = [
    ('Identity and design', 'case_id, sample_id, experiment_method, placement, run_id, split', 'One row is one query under one policy, not one physical setup.'),
    ('Question and provenance', 'question, book_id, source_url, evidence_quote, relevant_hashes_json', 'Synthetic source-linked labels are nonexhaustive and not human reviewed.'),
    ('Retrieved context and answer', 'answer, expected_answer, chunks_json, raw_response_json', 'Raw model output is preserved; expected_answer is not a human correctness judgment.'),
    ('Timing and routing', 'router_ms, aggregate_ms, generation_ms, client_ms, visited_nodes_json', 'Application timing separates routing, retrieval and generation.'),
    ('Worker instrumentation', 'miniN_embedding_ms, miniN_search_ms, miniN_round_trip_ms, miniN_status', 'Per-worker values are observed only when the worker is queried and the field is recorded.'),
    ('Traffic and transport', 'network_frame_bytes, miniN_network_ack_rtt_ms_mean, miniN_network_tx_mbps', 'Frame counts, TCP ACK RTT and window-averaged rates have distinct meanings.'),
]
csvwrite('dataset_field_groups.csv', [dict(group=a, examples=b, interpretation=c) for a,b,c in schema])

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
sec.top_margin, sec.bottom_margin = Inches(.67), Inches(.85)
sec.left_margin, sec.right_margin = Inches(.72), Inches(.72)
sec.header_distance, sec.footer_distance = Inches(.27), Inches(.3)
styles = doc.styles
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Caption']:
    styles[name].font.name = 'Calibri'
    styles[name].font.color.rgb = RGBColor(0,0,0)
styles['Normal'].font.size = Pt(10.3)
styles['Normal'].paragraph_format.line_spacing = 1.06
styles['Normal'].paragraph_format.space_after = Pt(5)
styles['Title'].font.size = Pt(23)
styles['Title'].paragraph_format.space_after = Pt(9)
styles['Heading 1'].font.size = Pt(16)
styles['Heading 1'].paragraph_format.space_before = Pt(8)
styles['Heading 1'].paragraph_format.space_after = Pt(8)
styles['Heading 2'].font.size = Pt(11.5)
styles['Heading 2'].paragraph_format.space_before = Pt(8)
styles['Heading 2'].paragraph_format.space_after = Pt(5)
styles['Caption'].font.size = Pt(9)
styles['Caption'].font.italic = False
styles['Caption'].font.bold = False
styles['Caption'].paragraph_format.space_after = Pt(8)
# The runtime starter document contains a themed title rule; remove all inherited
# paragraph borders so the scholarly title uses typography and whitespace only.
for style in styles:
    for border in list(style.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
footer = sec.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
footer.add_run('Distributed retrieval study  |  ')
fld = OxmlElement('w:fldSimple'); fld.set(qn('w:instr'), 'PAGE')
footer._p.append(fld)
for r in footer.runs: r.font.size=Pt(8)

def p(text, style=None):
    follows_table = len(doc._element.body)>1 and doc._element.body[-2].tag==qn('w:tbl')
    paragraph=doc.add_paragraph(text, style)
    if follows_table:
        paragraph.paragraph_format.space_before=Pt(6)
    return paragraph

def h(text, level=1):
    return doc.add_heading(text, level)

def page(title):
    heading=h(title)
    heading.paragraph_format.page_break_before=True

def table(headers, rows, widths=None, size=9):
    t=doc.add_table(rows=1, cols=len(headers))
    t.alignment=WD_TABLE_ALIGNMENT.CENTER
    t.autofit=False
    if widths:
        for c,w in zip(t.columns,widths): c.width=Inches(w)
    for c,text in zip(t.rows[0].cells,headers): c.text=str(text)
    for vals in rows:
        for c,text in zip(t.add_row().cells,vals): c.text=str(text)
    for i,row in enumerate(t.rows):
        trpr=row._tr.get_or_add_trPr()
        cant=OxmlElement('w:cantSplit');trpr.append(cant)
        if i==0:
            repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
        for j,c in enumerate(row.cells):
            if widths:c.width=Inches(widths[j])
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pr=c._tc.get_or_add_tcPr()
            margin=OxmlElement('w:tcMar')
            for edge in ['top','left','bottom','right']:
                v=OxmlElement('w:'+edge);v.set(qn('w:w'),'70');v.set(qn('w:type'),'dxa');margin.append(v)
            pr.append(margin)
            borders=OxmlElement('w:tcBorders')
            for edge in ['top','left','bottom','right']:
                b=OxmlElement('w:'+edge);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'4');b.set(qn('w:color'),'D9D9D9');borders.append(b)
            pr.append(borders)
            shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E8EBEE' if i==0 else ('F5F6F7' if i%2==0 else 'FFFFFF'));pr.append(shade)
            for para in c.paragraphs:
                para.paragraph_format.space_after=Pt(1)
                para.paragraph_format.line_spacing=1.02
                if j>0 and len(str(c.text))<28:para.alignment=WD_ALIGN_PARAGRAPH.CENTER
                for run in para.runs:
                    run.font.size=Pt(size);run.bold=(i==0);run.font.color.rgb=RGBColor(0,0,0)
    return t

def fig(stem, number, caption):
    for suffix in ['.png','.pdf','.caption.txt']:
        rel=f'figures/{stem}{suffix}'
        shutil.copy2(source(rel), OUT/rel)
    par=p('');par.paragraph_format.space_after=Pt(3);par.paragraph_format.keep_with_next=True
    run=par.add_run();run.add_picture(str(OUT/'figures'/f'{stem}.png'),width=Inches(6.78))
    # Meaningful alt text for the embedded figure.
    for node in run._r.xpath('.//wp:docPr'):node.set('descr',caption)
    p(f'Figure {number}. {caption}','Caption')

def caption(text):
    z=p(text,'Caption');z.paragraph_format.keep_with_next=True

# Page 1
p('Network and latency tradeoffs in distributed knowledge retrieval','Title')
p('Experimental methods and results with an empirical simulator', 'Subtitle')
h('Abstract',2)
p('We evaluated application-level distributed retrieval on four Apple M2 Mac mini computers with 8 GB memory each. A fixed corpus of 12 novels and 16,421 text chunks was queried with the same 500 synthetic questions under four policies, yielding 2,000 measured attempts. Semantic sequential routing reduced captured coordinator traffic by 33.5% relative to parallel broadcast, but increased mean retrieval latency from 338.6 to 952.4 ms. A consolidated database yielded the lowest observed latency and traffic at this corpus size. An empirical Monte Carlo simulator reproduced held-out mean retrieval latency within 4.0% and captured traffic within 5.6% in the measured configurations. Predictions at other worker counts remain assumption-based scenarios; they have not been validated as physical scaling results.')
h('1 Experimental system')
p('Mini-1 (192.168.50.11) hosted the HTTP coordinator, routing logic and answer model. Mini-2 through mini-4 (.12 to .14) exposed independent retrieval APIs and local Qdrant databases on an isolated Ethernet LAN. The coordinator called worker retrieval endpoints, merged and deduplicated results, selected global top-k context, and injected the context into the answer prompt. This is application-level distributed search, not Qdrant native clustering, model sharding or federated training.')
caption('Table 1. Categorical corpus placement before consolidation.')
table(['Worker and category','Books','Chunks'],[
    ['Mini-2  Gothic and speculative','Frankenstein; Dracula; Dr Jekyll and Mr Hyde; The Time Machine','4,529'],
    ['Mini-3  Detective','The Hound of the Baskervilles; The Adventures of Sherlock Holmes; A Study in Scarlet; The Sign of the Four','3,998'],
    ['Mini-4  Social and romance','Persuasion; Pride and Prejudice; Emma; Sense and Sensibility','7,894'],
], [1.55,4.4,.88],size=9)
p('All policies used the same canonical content. The single-database comparison copied all 16,421 vectors and payloads to a second Qdrant instance on mini-2; canonical IDs, hashes and payloads were verified, and the maximum vector-component difference was zero. Categorical partitions were not balanced by chunk count, so worker load differences must not be interpreted as pure routing effects.')
p('The archived service configuration specifies nomic-embed-text embeddings (768 dimensions, cosine similarity, query/document prefixes) and 512-character chunks with 64-character overlap. Answer generation used Ollama qwen3:1.7b, temperature 0, context 4,096 and at most 512 predicted tokens. Wi-Fi was disabled for experimental execution; the local services did not require internet access.')

# Page 2
page('2 Policies measurements and data structure')
table(['Policy','Search procedure'],[
    ['Semantic sequential','Embed the question locally, rank cached worker catalogue descriptions by cosine similarity, then visit workers in that order. No extra generative model call is used for routing.'],
    ['Parallel broadcast','Query all three workers concurrently, then merge their candidates.'],
    ['Random sequential','Visit a seeded random permutation of the categorical workers without replacement. Data placement is unchanged.'],
    ['Single database','Query the consolidated database on one worker through the same coordinator.'],
], [1.45,5.38],size=9.5)
p('The main comparison fixed the score threshold at 0.70, global top-k at 3 and per-worker candidate count at 5. Sequential policies stopped when three unique above-threshold chunks were accumulated, or after all workers were exhausted. This is a score-based stopping rule, not a test of semantic correctness. Candidate duplicates were removed by canonical content hash before global ranking. Failed workers and partial requests were recorded explicitly.')
h('Measurement definitions',2)
p('Aggregate retrieval time includes routing, worker calls and merging, but excludes answer generation. Client time is the full request duration. Worker timing separately records readiness, embedding, vector search and round-trip duration. Captured traffic is the sum of coordinator TX and RX frame lengths on worker HTTP ports 8000/8001 inside each query window; kB means 1,000 bytes. These values exclude physical link overhead and do not measure total Ethernet utilization. Summing the same packet at both endpoints would double-count it.')
p('The query windows include answer generation and can include delayed ACKs or health traffic. TCP ACK RTT estimates transport behavior; HTTP response time and application round-trip time also contain server processing. CSV Mbps fields are bytes divided by the query window, not link capacity or saturation throughput. Worker-side clocks were not synchronized, so cross-host wall-clock subtraction is not used for latency claims.')
h('Dataset organization',2)
p('Each row represents one question under one policy. The 500 questions were synthetic and source-quote verified, but not human reviewed. Reference labels are nonexhaustive. Hit@3 means that at least one labeled reference chunk appears among the first three results; miss@3 is its complement. It does not establish answer correctness or exhaustive recall. Two HTTP 503 attempts are retained; completed-request timing summaries omit them, while all-attempt traffic and hit rates retain all 500 attempts per policy.')
caption('Table 2. Selected column groups in the research dataset.')
table(['Group','Representative columns'],[(a,b) for a,b,c in schema], [1.65,5.18],size=8.5)
p('Raw responses and full node measurements remain available. The sample extracts preserve case IDs and full answers; all displayed examples are saved measurements.')

# Page 3
page('3 Measured latency traffic and retrieval outcomes')
fig('01_observed_tradeoff',1,'Observed latency and captured traffic at threshold 0.70. Latency uses completed requests; traffic uses all attempts. Error bars are question-bootstrap 95% confidence intervals of the mean, not between-session uncertainty. Source: figure01_data.csv.')
caption('Table 3. Primary observed results. Client time includes generation; traffic is captured frame kB per attempt. Mean visits use completed requests.')
table(['Policy','Done','Visits','Retrieval ms','p95 ms','kB','Client s','Hit@3'],[
    [LABELS[x['method']],f"{x['complete']}/500",f"{x['mean_visits_complete']:.2f}",f"{x['retrieval_mean_ms']:.1f}",f"{x['retrieval_p95_ms']:.1f}",f"{x['frame_bytes_mean_all_attempts']/1000:.2f}",f"{x['client_mean_ms']/1000:.2f}",f"{100*x['reference_hit_rate_all_attempts']:.1f}%"] for x in main_rows
], [1.54,.58,.49,.87,.66,.56,.65,.68],size=8.5)
p('Semantic routing reduced mean captured traffic from 18.56 to 12.35 kB per attempt (33.5%) relative to broadcast, and reduced mean visited workers from 3.00 to 1.98. However, mean retrieval latency was 2.81 times the broadcast value. The semantic router itself consumed 291.2 ms on average, and subsequent worker calls were sequential. Thus, fewer remote requests did not yield lower response time in this implementation.')
p('Random sequential routing used 22.0% less traffic than broadcast but had 2.15 times its mean retrieval latency. Semantic routing used 14.7% less traffic than random routing yet was 30.8% slower. These are observed cross-session comparisons; method and run session were partly confounded, so the differences do not isolate a universal causal routing effect.')
p('The consolidated database returned results in 310.4 ms with 6.15 kB per attempt: 8.3% lower retrieval latency and 66.9% less traffic than broadcast. The full corpus was served by one worker. These measurements favor consolidation at the tested size; they do not establish its behavior when memory, corpus size or concurrent load grows.')
p('Reference hit rates ranged from 40.8% to 42.8%. Broadcast found the marked passage in 214/500 attempts, compared with 204 for semantic, 207 for random and 213 for single database. These small descriptive differences have not been established as statistically significant, and reference hits must not be reported as answer accuracy.')
caption('Table 4. Coordinator transport summaries over completed queries. Values are unweighted means of per-query means or rates, not packet-weighted transport estimates.')
table(['Policy','ACK RTT ms','HTTP response ms','TX + RX Mbps'],[
    [LABELS[r['method']],f"{r['mean_of_query_mean_ack_rtt_ms']:.3f}",f"{r['mean_of_query_mean_http_response_ms']:.1f}",f"{r['mean_of_query_tx_plus_rx_mbps']:.4f}"] for r in transport
], [2.05,1.4,1.8,1.58],size=8.5)

# Page 4
page('4 Simulator construction and held out validation')
p('Question IDs were shuffled with seed 20261020 into 300 training, 100 validation and 100 frozen-test questions. All policies and derived permutations from one question remained in the same partition, following group-disjoint evaluation [2]. Model selection used only training and validation data; deployed calibration then used the first 400 questions. The frozen 100 questions contributed 400 complete method observations and were excluded from the calibration library.')
p('For native settings, Monte Carlo sampling draws a complete measured question-policy record, retaining the association between latency, traffic, visits, generation and reference labels. We used 10,000 draws per method. The reported p05/p95 values describe query variability; separately, 2,000 question-bootstrap replicates estimate 95% percentile intervals for the mean [3]. Resampling does not create new independent experimental evidence.')
fig('02_heldout_validation',2,'Calibration Monte Carlo means versus the 100 held-out questions per method in the native configurations. This tests question-level generalization within the recorded sessions, not new hardware, sessions or worker counts. Source: monte_carlo_validation.csv.')
caption('Table 5. Held-out mean comparison. Signed error is 100 × (simulation − measurement) / measurement. Traffic is shown in kB.')
table(['Policy','Metric','Simulated','Measured','Error'],[
    [LABELS[r['method']], {'aggregate_ms':'Retrieval ms','network_frame_bytes':'Traffic kB','client_ms':'Client ms'}[r['target']],
     f"{float(r['simulated_mean'])/(1000 if r['target']=='network_frame_bytes' else 1):.2f}",
     f"{float(r['test_mean'])/(1000 if r['target']=='network_frame_bytes' else 1):.2f}", f"{float(r['mean_error_percent']):+.2f}%"] for r in validation
], [1.7,1.35,1.2,1.2,1.18],size=8)
p('Mean retrieval errors were −3.99% to +0.19%, and traffic errors were −5.53% to +0.15%. End-to-end client means were consistently underestimated by 8.40–10.06%, indicating a weaker fit for the combined generation workload. Small mean error is a distribution-level result, not a per-query accuracy percentage. The numerical CSV also preserves p95 errors and calibration confidence intervals.')

# Page 5
page('5 Regression baselines and algorithm verification')
p('We compared a per-method mean baseline with a standardized Ridge regression implemented in NumPy. Inputs were policy indicators, question UTF-8 byte length and word count, all known before execution. Realized visits, response size, score, hit and answer length were excluded to avoid future-information leakage. The Ridge objective was squared error plus an L2 penalty on coefficients, with an unpenalized intercept [1]. Alpha was selected by validation MAE from 0.1, 1, 10, 100 and 1,000.')
fig('05_regression_baselines',3,'Frozen-test mean absolute error for the method-mean baseline and Ridge. Model selection preceded evaluation on the 100 held-out questions. All candidate results, including weak results, are retained. Source: model_validation.json.')
caption('Table 6. Frozen-test point-prediction comparison across 400 complete method observations.')
table(['Target','Mean MAE','Ridge MAE','Selected','Selected R²'],[
    [label,f"{regression[k]['frozen_test_baseline']['mae']:.2f}",f"{regression[k]['frozen_test_ridge']['mae']:.2f}",regression[k]['selected_on_validation'],f"{regression[k]['frozen_test_selected']['r2']:.3f}"]
    for k,label in [('aggregate_ms','Retrieval ms'),('network_frame_bytes','Traffic bytes'),('client_ms','Client ms')]
], [1.4,1.2,1.2,1.55,1.28],size=9)
p('Ridge did not improve retrieval or traffic MAE, so the simpler method mean was retained for those point predictions. Ridge reduced client MAE by only 7.78 ms (about 1.0%), with R² = 0.025. Pooled R² for retrieval and traffic largely reflects differences between policies; the selected models had negative R² within each individual policy. The available question-length features therefore provide little evidence of useful within-policy prediction.')
h('Replay and derived data',2)
p('The replay implementation reproduced visited-node sequences and final returned content hashes exactly for all 1,998 successful original observations. This verifies execution logic, not predictive generalization. Enumerating all six worker visit permutations for each question produced 3,000 derived rows. Source case IDs, split labels and synthetic status were retained; frozen-test derivatives were excluded from calibration. Derived timings were not used as independent real targets for Ridge training.')
p('The simulator separates three evidence levels: empirical resampling at measured settings, counterfactual replay of saved candidates, and explicitly assumed virtual-worker scenarios. An interface can expose these as controls, but it cannot convert unmeasured settings into validated predictions.')

# Page 6
page('6 Threshold sensitivity and auxiliary experiments')
fig('04_threshold_replay',4,'Counterfactual threshold replay from 0.0 to 1.0 in steps of 0.1 using recorded top-five candidates from 400 calibration questions, resampled 5,000 times per setting. Blue star: semantic; green square: broadcast; orange triangle: random, consistently across line charts. No new searches or answers were generated. Rates are reference hits, not answer accuracy. Source: threshold_trace_replay.csv.')
caption('Table 7. Selected replay thresholds; the figure and source CSV cover every 0.1 step from 0.0 to 1.0. Each cell is reference-hit percentage / mean visits.')
table(['Threshold','Semantic','Broadcast','Random'],[
    [f'{t:.2f}'] + [f"{100*float(next(r for r in thresholds if float(r['threshold'])==t and r['method']==m)['reference_hit_rate']):.2f}% / {float(next(r for r in thresholds if float(r['threshold'])==t and r['method']==m)['mean_visits']):.2f}" for m in METHODS[:3]] for t in [.0,.70,.80,1.0]
], [1.0,1.95,1.94,1.94],size=9)
p('Increasing the threshold made early stopping less likely. At 0.80, both sequential policies visited almost all three workers and replay reference hits fell to about 4.2%; at 0.90 and 1.00 no marked references survived. From 0.00 through 0.50, both sequential policies stopped after one worker: semantic reference hits were 32.24%, versus 17.82% for random and 48.98% for broadcast. Early stopping can accept plausible fragments without the marked passage, so a lower threshold need not improve reference retrieval.')
p('The replay at 0.70 is not expected to equal the full observed hit rate exactly: it uses the 400-question calibration subset, finite resampling and saved candidate lists. Replay is limited to the recorded top five candidates per worker; it cannot recover candidates absent from those lists, estimate new ANN results or evaluate newly generated answers.')
h('Separate measured runs at threshold 0.80',2)
caption('Table 8. Auxiliary physical runs excluded from the matched-threshold main comparison.')
table(['Measured auxiliary run','Attempts','Reference hits','Generation','No context'],[
    ['Random node order',500,'23 (4.6%)',30,470],
    ['Single database',500,'23 (4.6%)',30,470],
], [2.15,.85,1.35,1.1,1.38],size=9)
p('These 1,000 additional real attempts were archived as auxiliary evidence and excluded from the matched-threshold main comparison. They were not all misses: each run contained 23 reference hits. However, 94% of queries produced no usable context and did not invoke the answer model. A strict similarity threshold can reduce generation work by withholding context while also severely limiting coverage; this workload differs from the main 0.70 condition.')

# Page 7
page('7 Virtual worker scenarios and their limits')
fig('03_scaling_assumptions',5,'Unvalidated virtual-worker scenarios. Curves reuse measured cost and payload archetypes with one owner and N−1 distractors; semantic owner-first probability is assumed 0.57. Blue star: semantic; green square: broadcast; orange triangle: random, as in Figure 4. These curves are not physical scaling measurements. Source: scaling_assumptions.csv.')
p('The assumption engine supports one content-owner profile and additional distractor profiles, with distinct virtual IDs and content hashes. Sequential cost sums routing and visited-worker times; broadcast uses the slowest parallel worker time. An optional slower shared-link setting adds an assumed transfer penalty once. No hardware-speed, corpus-size, queueing, saturation or WAN coefficient was learned from the experiments.')
caption('Table 9. Example assumption-mode outputs. Values are simulated retrieval ms / estimated frame kB per query; 3,000 draws per setting.')
table(['Virtual workers','Semantic','Broadcast','Random'],[
    [n]+[f"{float(next(r for r in scaling if int(r['nodes'])==n and r['method']==m)['mean_ms']):.0f} / {float(next(r for r in scaling if int(r['nodes'])==n and r['method']==m)['mean_frame_bytes'])/1000:.2f}" for m in METHODS[:3]] for n in [3,8,16]
], [1.0,1.95,1.94,1.94],size=9)
p('Under these assumptions, broadcast traffic grows approximately linearly with worker count while modeled latency stays near one worker service time. That flat curve follows the uncongested parallel-cost assumption; it is not evidence that a real system can add workers without latency or bandwidth penalties. Sequential traffic can remain lower, but extra visits increase latency. New worker counts deliberately have no predicted hit rate.')
p('The virtual three-worker scenario is not the native empirical mode, and its values need not equal measured three-worker averages. The same one-owner archetype assumption is used for every N; it does not model repartitioning a fixed corpus or holding data per worker constant. The current simulator is useful for transparent what-if comparisons within these limits [4].')

# Page 8
page('8 Concrete query examples from the dataset')
sample = next(r for r in by_case['pg35-027'] if r['experiment_method']=='semantic_sequential')
p('Example A illustrates a reference hit with early stopping. Case pg35-027 comes from The Time Machine. Question and outputs below are real saved records, selected for explanation rather than as a representative random sample.')
p('Question: '+sample['question'])
p('Reference answer: '+sample['expected_answer']+'.')
p('Source evidence: “'+sample['evidence_quote']+'”')
p('Recorded semantic answer excerpt: “'+sample['answer'].split('\n')[0]+'”')
caption('Table 10. The same question under all four policies. Traffic is captured frame bytes, not HTTP body bytes.')
table(['Policy','Visited workers','Retrieval ms','Client ms','Frame bytes','Hit'],[
    [LABELS[m],', '.join(json.loads(next(r for r in by_case['pg35-027'] if r['experiment_method']==m)['visited_nodes_json'])),
     f"{float(next(r for r in by_case['pg35-027'] if r['experiment_method']==m)['aggregate_ms']):.1f}",
     f"{float(next(r for r in by_case['pg35-027'] if r['experiment_method']==m)['client_ms']):.1f}",
     f"{float(next(r for r in by_case['pg35-027'] if r['experiment_method']==m)['network_frame_bytes']):.0f}",
     next(r for r in by_case['pg35-027'] if r['experiment_method']==m)['hit_at_k']] for m in METHODS
], [1.55,1.53,.97,.87,1.2,.41],size=8.5)
p(f"The semantic request visited only mini-2, with 289.0 ms of routing inside 619.9 ms retrieval. The worker recorded {float(sample['mini2_readiness_ms']):.1f} ms readiness, {float(sample['mini2_embedding_ms']):.1f} ms embedding and {float(sample['mini2_search_ms']):.1f} ms vector search. The accompanying CSV retains full answers, reference evidence, worker timing and network fields, visit order and split labels.")
miss = next(r for r in by_case['pg244-008'] if r['experiment_method']=='semantic_sequential')
h('Early stopping can return context without a reference hit',2)
p('Example B, case pg244-008, asks: “'+miss['question']+'” The stored reference answer is “'+miss['expected_answer']+'” The semantic result instead began: “'+miss['answer'].split('\n')[0]+'” It visited mini-4 and stopped after collecting three accepted chunks; the marked detective reference belongs to mini-3. Hit@3 was 0, although HTTP status was 200 and generation completed.')
p('This example shows why request success, a high similarity score, reaching the chunk target and finding the labeled reference are separate outcomes. The question is also underspecified without a book identifier, illustrating a limitation of the synthetic question set. The record does not support a claim that every off-reference answer is wrong; it supports the narrower claim that the labeled source passage was not retrieved.')
h('A hit is not an answer correctness certificate',2)
p('Example C, pg2852-015, has Hit@3 = 1, but its stored reference describes a sound behind the narrator while the generated answer discusses a shadowy plain and an old tin mine. This discrepancy motivates human answer review. We retain the full output in the sample CSV and do not use the hit label as an answer-accuracy score.')

# Page 9
page('9 Reproducibility interpretation and next experiments')
h('Evidence preservation',2)
p('The research package stores immutable raw CSV/JSONL responses, corpus files, questions, canonical chunks, packet captures, source scripts and a 132-file SHA-256 input manifest. The report directory contains the editable document, a rendered PDF, all five original figures in PNG/PDF with captions, extracted numerical tables, sample query rows and a source checksum manifest. The build script reads existing results; it does not rerun retrieval or retrain models.')
p('All 2,000 query-window byte totals were independently recomputed from archived packet captures and matched the dataset exactly. The older capture had an incomplete trailing record removed while preserving its original; its kernel-drop count is unknown. The restarted capture recorded zero kernel drops and all 1,672 worker request/response pairs were matched. The existing project verification also records 13 numerical/flow/split tests, 8 local API checks and a clean installation from local wheel files.')
h('Limitations that bound the claims',2)
p('There was one measured observation per question and policy at concurrency one; the 500 questions are not 500 independent deployment sessions. Policy and session effects were partly confounded. Bootstrap intervals capture question sampling variation, not run-to-run system variation. Clocks were unsynchronized across hosts, and captured query-window bytes are not complete physical wire utilization. Synthetic, nonexhaustive relevance labels and ambiguous questions limit quality interpretation.')
p('Only the native one-worker consolidated configuration and three-worker categorical configuration were physically tested. Random sequential denotes randomized visit order, not randomized chunk placement. The data therefore do not identify an independent effect of worker count, corpus size, hardware, network capacity or offered load. Augmented visit permutations and Monte Carlo draws do not increase the number of independent physical observations. No claim is made about maximum throughput, WAN operation or production reliability.')
h('Implications and next experiments',2)
p('At the measured scale, semantic routing trades less captured traffic for more retrieval time, parallel broadcast favors latency, and consolidation is the most economical observed configuration. The empirical simulator can reproduce method-level means for held-out questions from this workload; the simple question features do not yield strong within-policy point predictions. The virtual-worker mode should be used to inspect assumptions and prioritize measurements.')
p('The next study should vary real worker count while keeping the corpus fixed, then separately hold data per worker constant. It should add truly randomized chunk placement, repeated sessions with randomized policy order, synchronized clocks, concurrent-load sweeps and reviewed relevance/answer labels. These measurements would allow worker count, data size and queueing effects to be estimated independently rather than assumed.')
h('Method references',2)
reference_titles = [
    'scikit-learn. Ridge regression objective and L2 regularization.',
    'scikit-learn. GroupShuffleSplit and group-disjoint evaluation.',
    'SciPy. Bootstrap resampling and confidence intervals.',
    'NIST Engineering Statistics Handbook. Model use beyond the experimental region.',
]
for i,(r,title) in enumerate(zip(refs,reference_titles),1):
    pp=p(f'[{i}] {title} {r["url"]}')
    pp.paragraph_format.space_after=Pt(4)
    for run in pp.runs:run.font.size=Pt(8)
p('Reference HTML snapshots and their checksums are archived in the project. Ridge, grouped splitting and percentile bootstrap were implemented in NumPy; scikit-learn and SciPy are methodological references, not runtime requirements.').runs[0].font.size=Pt(8)

doc.core_properties.title = 'Network and latency tradeoffs in distributed knowledge retrieval'
doc.core_properties.subject = 'Experimental methods, measured results and empirical simulator validation'
doc.core_properties.author = ''
doc.core_properties.keywords = 'distributed retrieval, RAG, network traffic, latency, Monte Carlo'
doc.save(OUT/'distributed_retrieval_report.docx')

manifest=[]
for rel in sorted(USED):
    path=ROOT/rel
    manifest.append(dict(path='../'+rel, bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
(OUT/'source_manifest.json').write_text(json.dumps(dict(
    report_date='2026-10-22',visual_revision_date='2026-10-23', dataset_rows=len(observations), questions=len(by_case),
    measured_main_threshold=.70, example_case_ids=example_ids, sources=manifest,
    scope='Existing measurements and saved simulator outputs only; no new physical experiments or model fitting.'
),indent=2))
(OUT/'report_checks.json').write_text(json.dumps(dict(
    main_rows=len(observations), unique_questions=len(by_case),
    method_counts={m:sum(r['experiment_method']==m for r in observations) for m in METHODS},
    complete=sum(r['complete']=='True' for r in observations),
    samples=len(examples), figures=5, tables=11, numbered_tables=10,
    byte_recalculation_all_match=pcap['all_match'],
    synthetic_rows_counted_as_real=False, scaling_claimed_as_measured=False,
    answer_accuracy_claimed=False, render_review='pending'
),indent=2))
print(OUT/'distributed_retrieval_report.docx')
