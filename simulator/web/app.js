"use strict";
const $ = id => document.getElementById(id);
const names = {
  broadcast: "Search all computers at once",
  semantic_sequential: "Try the most relevant computer first",
  random_sequential: "Try computers in a random order",
  single_db: "Keep all documents on one computer"
};
const methodNotes = {
  broadcast: "Checks every search computer at the same time, then combines the results.",
  semantic_sequential: "Checks computers one by one, starting with the one whose documents seem most relevant. Stops after enough matching passages are found.",
  random_sequential: "Checks randomly chosen computers one by one. Stops after enough matching passages are found, or after checking every computer.",
  single_db: "Searches all source documents on one computer. No other search computers are contacted."
};
const number = (value, digits=0) => new Intl.NumberFormat("en-US", {
  maximumFractionDigits: digits, minimumFractionDigits: digits
}).format(value);
let latest = null, requestNumber = 0;

function modeControls() {
  const mode = $("mode").value;
  const assumption = mode === "assumption", empirical = mode === "empirical";
  const single = $("method").querySelector('[value="single_db"]');
  single.disabled = !empirical;
  if (!empirical && $("method").value === "single_db") $("method").value = "broadcast";
  $("nodes").disabled = !assumption;
  if (!assumption) $("nodes").value = $("method").value === "single_db" ? 1 : 3;
  $("threshold").disabled = empirical;
  $("top-k").disabled = empirical;
  if (empirical) { $("threshold").value = "0.70"; $("top-k").value = "3"; }
  $("assumption-fields").hidden = !assumption;
  $("assumption-fields").querySelectorAll("input").forEach(input => input.disabled = !assumption);
  const semanticAssumption = assumption && $("method").value === "semantic_sequential";
  $("owner-field").hidden = !semanticAssumption;
  $("owner-probability").disabled = !semanticAssumption;
  $("owner-probability").required = semanticAssumption;
  $("method-note").textContent = methodNotes[$("method").value];
  $("mode-note").textContent = empirical
    ? "Estimates based on our real tests with one or three search computers."
    : assumption
      ? "Change the number of computers and network settings. Results depend on your assumptions and have not been tested on that new setup."
      : "Change which passages count as a match, using recorded results from three computers. No new document searches are performed.";
  $("nodes-note").textContent = assumption
    ? "One separate computer coordinates the search and is not counted here. Extra search computers are simulated, not physically tested."
    : "To change the computer count, choose “Explore a different setup” above. One separate computer coordinates the search and is not counted here.";
  $("threshold-note").textContent = empirical
    ? "0.70 is the tested match score. To adjust it, choose “Try different match settings”. This score is not answer accuracy."
    : "A higher score accepts fewer passages and may require checking more computers. It is not the chance of a correct answer.";
}

function configuration() {
  const mode = $("mode").value;
  const c = {
    method: $("method").value, mode, nodes: Number($("nodes").value),
    threshold: Number($("threshold").value), top_k: Number($("top-k").value),
    draws: Number($("draws").value), seed: Number($("seed").value),
    include_generation: $("generation").checked
  };
  if (mode === "assumption") {
    c.extra_rtt_ms = Number($("extra-rtt").value);
    c.service_time_multiplier = Number($("service-multiplier").value);
    if ($("bandwidth").value.trim() !== "") {
      c.bandwidth_mbps = Number($("bandwidth").value);
      c.reference_bandwidth_mbps = Number($("reference-bandwidth").value);
    }
    if (c.method === "semantic_sequential") {
      c.semantic_owner_first_probability = Number($("owner-probability").value)/100;
    }
  }
  return c;
}

function time(value) {
  return value === null ? ["—", ""]
    : value >= 1000 ? [number(value/1000,2), "s"] : [number(value), "ms"];
}
function formatTime(value) { return time(value).join(" "); }
function metric(id, value) {
  const [v,u] = time(value);
  $(id+"-value").textContent = v;
  $(id+"-unit").textContent = u;
}

function render(result) {
  const c = result.config, s = result.summary;
  const assumed = c.mode === "assumption", trace = c.mode === "trace";
  $("result-title").textContent = names[c.method];
  $("result-subtitle").textContent = `${number(c.nodes)} search ${c.nodes===1?"computer":"computers"} · match score ${number(c.threshold,2)} · collect ${c.top_k} passages`;
  $("evidence-badge").textContent = assumed
    ? "Based on assumptions" : trace ? "Replayed from records" : "Checked against our tests";
  $("evidence-badge").className = "badge"+(assumed?" assumption":trace?" trace":"");
  metric("latency",s.retrieval_ms.mean);
  metric("p95",s.retrieval_ms.p95);
  $("traffic-value").textContent = number(s.network_frame_bytes.mean/1000,1);
  $("visits-value").textContent = number(s.visited_nodes.mean,2);
  $("generation-result").hidden = !c.include_generation;
  $("total-value").textContent = formatTime(s.end_to_end_ms.mean);
  const contacts = c.nodes === 1 ? "It contacts one search computer."
    : c.method === "broadcast"
    ? `It contacts all ${c.nodes} search computers.`
    : `It contacts about ${number(s.visited_nodes.mean,1)} of the ${c.nodes} search computers on average before stopping.`;
  $("takeaway").textContent = `With this setup, finding source passages takes about ${formatTime(s.retrieval_ms.mean)} and transfers ${number(s.network_frame_bytes.mean/1000,1)} kB per search on average. ${contacts}`;
  $("scope").className = "scope"+(assumed?" assumption":"");
  $("scope-title").textContent = assumed
    ? "A what-if estimate, not a tested result"
    : trace ? "Existing search results, tried in a different way" : "What has been checked?";
  $("scope-description").textContent = assumed
    ? "Extra computers reuse the timing and message patterns from our tests. New computer counts have not been tested in real life. Busy networks, waiting queues and larger document collections are not modeled."
    : trace
      ? "The simulator reuses the five recorded candidate passages from each of three computers. Changing the match settings changes when it stops. Timing and traffic are estimates; it does not run new searches or check answer correctness."
      : "Average results were compared with 100 questions kept out of model calibration, on the same hardware and document collection. This does not establish accuracy for new hardware or many searches running at once.";
  $("draw-count").textContent = number(c.draws)+" simulated searches";
  const rows = [
    ["Search time", s.retrieval_ms, formatTime],
    ["Network data", s.network_frame_bytes, v=>number(v/1000,2)+" kB"],
    ["Message contents only", s.application_body_bytes, v=>number(v/1000,2)+" kB"],
    ["Computers contacted", s.visited_nodes, v=>number(v,2)]
  ];
  if (c.include_generation) rows.push(["Total time with AI writing", s.end_to_end_ms, formatTime]);
  $("distribution-body").replaceChildren(...rows.map(([label,stats,fmt])=>{
    const tr = document.createElement("tr");
    [label,fmt(stats.mean),fmt(stats.p50),fmt(stats.p95)].forEach(text=>{
      const td = document.createElement("td");td.textContent = text;tr.appendChild(td);
    });
    return tr;
  }));
  $("failure-note").textContent = result.failed_draws
    ? `${number(result.failed_draws)} repetitions sampled a failed search record. Averages above cover completed repetitions only.`
    : "No failed searches were sampled in this run. These are simulated repetitions, not new physical tests.";
  $("download").disabled = false;
  $("download-json").disabled = false;
}

function markDirty() {
  if (!latest) return;
  $("result-status").className = "result-status dirty";
  $("result-status").textContent = "Settings changed. Select Estimate results to update the numbers below.";
}

async function run(event) {
  if (event) event.preventDefault();
  $("scenario-form").querySelectorAll("input").forEach(input=>{
    input.setCustomValidity("");input.removeAttribute("aria-invalid");
  });
  if (!$("scenario-form").checkValidity()) {
    const invalid = $("scenario-form").querySelector("input:invalid");
    if (invalid && $("advanced").contains(invalid)) $("advanced").open = true;
    if (invalid) {
      const label = document.querySelector(`label[for="${invalid.id}"]`).textContent.trim().replace(/\s+/g," ");
      const message = invalid.validity.valueMissing ? `${label} is required.`
        : invalid.validity.rangeOverflow || invalid.validity.rangeUnderflow
          ? `Use a value between ${invalid.min} and ${invalid.max} for ${label.toLowerCase()}.`
          : invalid.validity.stepMismatch
            ? `Use increments of ${invalid.step} for ${label.toLowerCase()}.`
            : `Enter a valid number for ${label.toLowerCase()}.`;
      invalid.setCustomValidity(message);invalid.setAttribute("aria-invalid","true");
      $("form-error").textContent=message;$("form-error").hidden=false;
      invalid.focus();invalid.reportValidity();
    }
    return;
  }
  const token = ++requestNumber, config = configuration();
  $("form-error").hidden = true;
  $("run").disabled = true;
  $("run-label").textContent = "Estimating…";
  $("run-icon").textContent = "…";
  $("results-panel").setAttribute("aria-busy","true");
  $("result-status").className = "result-status";
  $("result-status").textContent = "Estimating from recorded searches. No live searches are being sent.";
  try {
    const response = await fetch("/v1/simulate",{
      method: "POST",headers: {"Content-Type":"application/json"},body: JSON.stringify(config)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(response.status === 422
      ? "These settings cannot be used together. Check your values or choose a different setup above."
      : "The estimate could not be completed. Please try again.");
    if (token !== requestNumber) return;
    latest = data;
    render(data);
    $("result-status").textContent = "Estimate ready · no live searches were sent";
    if (JSON.stringify(config) !== JSON.stringify(configuration())) markDirty();
  } catch (error) {
    $("form-error").textContent = error instanceof TypeError
      ? "Cannot reach the local simulator. Start it with start.command, then try again."
      : error.message;
    $("form-error").hidden = false;
    $("result-status").textContent = latest
      ? "Showing the previous estimate. The new calculation did not complete." : "No estimate yet. Please try again.";
  } finally {
    if (token === requestNumber) {
      $("run").disabled = false;
      $("run-label").textContent = "Estimate results";
      $("run-icon").textContent = "→";
      $("results-panel").setAttribute("aria-busy","false");
    }
  }
}

function download(data,extension,type) {
  const url = URL.createObjectURL(new Blob([data],{type}));
  const a = document.createElement("a");
  a.href = url;
  a.download = `search-simulation-${latest.config.method}-${latest.config.nodes}-computers.${extension}`;
  a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

$("scenario-form").addEventListener("submit",run);
$("scenario-form").addEventListener("input",event=>{
  if (event.target instanceof HTMLInputElement) {
    event.target.setCustomValidity("");event.target.removeAttribute("aria-invalid");
  }
  markDirty();
});
$("mode").addEventListener("change",()=>{modeControls();markDirty();});
$("method").addEventListener("change",()=>{modeControls();markDirty();});
$("reset").addEventListener("click",()=>{
  $("scenario-form").reset();$("advanced").open = false;modeControls();run();
});
$("download").addEventListener("click",()=>{
  if (!latest) return;
  const c = latest.config, s = latest.summary;
  const report = {
    search_method: names[c.method], setup: c.mode, evidence: latest.evidence_level,
    search_computers: c.nodes, match_score: c.threshold, target_passages: c.top_k,
    repetitions: c.draws, seed: c.seed,
    average_search_ms: s.retrieval_ms.mean, median_search_ms: s.retrieval_ms.p50,
    p95_search_ms: s.retrieval_ms.p95, average_network_kB: s.network_frame_bytes.mean/1000,
    average_computers_contacted: s.visited_nodes.mean, includes_AI_writing: c.include_generation,
    average_total_ms: s.end_to_end_ms.mean, failed_repetitions: latest.failed_draws, run_id: latest.run_id
  };
  const escape = value => '"'+String(value ?? "").replaceAll('"','""')+'"';
  const csv = '\uFEFF'+[Object.keys(report),Object.values(report)].map(row=>row.map(escape).join(',')).join('\r\n')+'\r\n';
  download(csv,"csv","text/csv;charset=utf-8");
});
$("download-json").addEventListener("click",()=>{
  if (latest) download(JSON.stringify(latest,null,2),"json","application/json");
});
modeControls();
run();
