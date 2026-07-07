const API = "";

let currentRun = null;

let currentStep = 0;

let selectedNewsId = null;

let eventSource = null;
let thinkingBuffer = "";
let sseIntentionalClose = false;
let isResolving = false;



const AGENT_NAMES = [

  "NewsCollector", "ComponentMapper", "BottleneckAnalyzer",

  "QuantValidator", "SupplierScreener", "ReportWriter"

];



function setStatus(msg) {

  const el = document.getElementById("status-msg");

  if (el) el.textContent = msg || "";

}



function renderStepBar(step) {

  const bar = document.getElementById("step-bar");

  bar.innerHTML = AGENT_NAMES.map((name, i) =>

    `<div class="step ${i === step ? "active" : ""}">step${i} ${name}</div>`

  ).join("");

}



function appendLog(data) {

  const logEl = document.getElementById("event-log");

  if (!logEl) return;

  const event = data.event || "unknown";

  if (event === "heartbeat") return;



  const line = document.createElement("div");

  line.className = `log-line log-${event}`;



  if (event === "agent_progress") {

    const kind = data.kind || "progress";

    if (kind === "thinking" || kind === "llm_output") {

      line.className = `log-line log-thinking`;

      if (kind === "thinking") {

        thinkingBuffer += data.message || "";

        line.textContent = data.message || "";

      } else {

        line.textContent = data.message || "";

      }

      logEl.appendChild(line);

      logEl.scrollTop = logEl.scrollHeight;

      return;

    }

    line.textContent = `[Agent${data.agent || "?"}] ${data.message || ""}`;

  } else if (event === "agent_start") {

    thinkingBuffer = "";

    line.textContent = `>> Agent${data.agent} ${data.agent_name} 开始`;

  } else if (event === "agent_complete") {

    line.textContent = `<< Agent${data.agent} 完成: ${data.summary || ""}`;

  } else if (event === "step_approval_required") {

    line.textContent = `== step${data.step} 待确认: ${data.step_output_summary || ""}`;

  } else if (event === "step_resolved") {

    line.textContent = `-- step${data.step} ${data.action}`;

  } else if (event === "run_start") {

    line.textContent = `## Run 开始 (${data.run_date || ""})`;

  } else if (event === "run_complete") {

    line.textContent = "## 流程完成";

  } else if (event === "run_error" || event === "agent_error") {

    line.textContent = `!! 错误: ${data.error || ""}`;

    line.className = "log-line log-error";

  } else {

    line.textContent = JSON.stringify(data);

  }



  logEl.appendChild(line);

  logEl.scrollTop = logEl.scrollHeight;

}



function connectSSE(runId) {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  sseIntentionalClose = false;
  const logEl = document.getElementById("event-log");
  if (logEl) logEl.innerHTML = "";
  thinkingBuffer = "";

  eventSource = new EventSource(`${API}/runs/${runId}/events`);
  eventSource.onmessage = (ev) => {
    let data;
    try {
      data = JSON.parse(ev.data);
    } catch {
      return;
    }
    appendLog(data);

    if (data.event === "agent_start") {
      setStatus(`Agent${data.agent} ${data.agent_name} 运行中…`);
      document.getElementById("btn-proceed").disabled = true;
    }
    if (data.event === "agent_complete") {
      refreshView();
    }
    if (data.event === "step_approval_required") {
      isResolving = false;
      currentStep = data.step;
      applyApprovalView(data);
      setStatus(data.step_output_summary || `step${data.step} 待确认`);
      document.getElementById("btn-proceed").disabled = !!(data.approval_hints && data.approval_hints.block_proceed);
      document.getElementById("btn-rerun").disabled = false;
      document.getElementById("btn-change").style.display = data.step >= 1 ? "inline-block" : "none";
      document.getElementById("btn-change").disabled = false;
    }
    if (data.event === "run_complete") {
      sseIntentionalClose = true;
      eventSource.close();
      document.getElementById("report-panel").classList.remove("hidden");
      fetch(`${API}/runs/${runId}`)
        .then((r) => r.json())
        .then((run) => {
          document.getElementById("report-md").textContent = run.final_report_md || "";
        });
      setStatus("流程已完成");
      document.getElementById("btn-proceed").disabled = true;
    }
    if (data.event === "run_error" || data.event === "agent_error") {
      isResolving = false;
      setStatus(`运行失败: ${data.error || ""}`);
      document.getElementById("btn-proceed").disabled = false;
      document.getElementById("btn-rerun").disabled = false;
      document.getElementById("btn-change").disabled = false;
      refreshView();
    }
  };
  eventSource.onerror = () => {
    if (sseIntentionalClose) return;
    setStatus("连接波动，正在重连…（若长时间无响应请刷新页面）");
  };
}



function applyApprovalView(data) {

  renderStepBar(data.step);

  const view = {

    step: data.step,

    output: data.output,

    approval_hints: data.approval_hints || {},

  };

  renderOutput(view);

  const hints = view.approval_hints || {};

  const hintsEl = document.getElementById("hints");

  const msgs = hints.messages || [];

  if (hints.block_proceed || msgs.length) {

    hintsEl.classList.remove("hidden");

    hintsEl.textContent = msgs.join(" ") || "请注意门控提示";

  } else {

    hintsEl.classList.add("hidden");

  }

}



function renderOutput(view) {

  const outputEl = document.getElementById("output");

  const step = view.step;



  if (step === 0 && view.output && view.output.news_items) {

    const items = view.output.news_items;

    if (!items.length) {

      outputEl.innerHTML = "<p>暂无新闻，请点击「重跑本步」重试。</p>";

      return;

    }

    outputEl.innerHTML = `

      <p class="step-hint">请选择 1 条硬件向热点，再点击「满意，下一步」：</p>

      <div class="news-list">

        ${items.map((n) => `

          <label class="news-card">

            <input type="radio" name="news_id" value="${n.id}" ${selectedNewsId === n.id ? "checked" : ""} />

            <div class="news-body">

              <strong>${escapeHtml(n.title)}</strong>

              <p>${escapeHtml(n.summary || "")}</p>

              <small>${escapeHtml(n.source || "")} · heat ${n.heat_score ?? "-"}</small>

            </div>

          </label>

        `).join("")}

      </div>`;

    outputEl.querySelectorAll('input[name="news_id"]').forEach((input) => {

      input.addEventListener("change", (e) => {

        selectedNewsId = e.target.value;

      });

    });

    if (!selectedNewsId && items[0]) {

      selectedNewsId = items[0].id;

      const first = outputEl.querySelector('input[name="news_id"]');

      if (first) first.checked = true;

    }

    return;

  }



  outputEl.textContent = JSON.stringify(view.output, null, 2);

}



function escapeHtml(s) {

  return String(s)

    .replace(/&/g, "&amp;")

    .replace(/</g, "&lt;")

    .replace(/>/g, "&gt;")

    .replace(/"/g, "&quot;");

}



async function createRun() {

  setStatus("正在创建任务并连接实时日志…");

  document.getElementById("btn-proceed").disabled = true;

  try {

    const resp = await fetch(`${API}/runs`, {

      method: "POST",

      headers: { "Content-Type": "application/json" },

      body: JSON.stringify({ run_date: new Date().toISOString().slice(0, 10) })

    });

    if (!resp.ok) {

      const err = await resp.json().catch(() => ({}));

      setStatus(`创建失败: ${err.detail || resp.status}`);

      return;

    }

    const data = await resp.json();

    currentRun = data.run_id;

    currentStep = data.pending_approval_step ?? 0;

    selectedNewsId = null;

    connectSSE(currentRun);
    setStatus(`run_id: ${currentRun} · 后台执行中，请查看实时日志`);
    setTimeout(() => refreshView(), 8000);
    if (data.status === "awaiting_step_approval") {
      await refreshView();
    }

  } catch (e) {

    setStatus(`网络错误: ${e.message}`);

  }

}



async function refreshView() {
  if (!currentRun) return;
  const runResp = await fetch(`${API}/runs/${currentRun}`);
  if (runResp.ok) {
    const run = await runResp.json();
    if (run.pending_approval_step != null) {
      currentStep = run.pending_approval_step;
    }
    if (run.status === "awaiting_step_approval" && run.pending_approval_step != null) {
      const resp = await fetch(`${API}/runs/${currentRun}/steps/${currentStep}`);
      if (resp.ok) {
        applyApprovalView(await resp.json());
        setStatus(run.step_output_summary || `step${currentStep} 待确认`);
        document.getElementById("btn-proceed").disabled = false;
        document.getElementById("btn-change").style.display = currentStep >= 1 ? "inline-block" : "none";
        return;
      }
    }
    setStatus(`当前状态: ${run.status}，待确认 step=${run.pending_approval_step ?? "-"}`);
    return;
  }
  const resp = await fetch(`${API}/runs/${currentRun}/steps/${currentStep}`);
  if (resp.ok) {
    applyApprovalView(await resp.json());
  }
}



async function resolve(action, newsId) {
  if (isResolving) return;
  isResolving = true;
  setStatus("已提交，后台执行中…");
  document.getElementById("btn-proceed").disabled = true;
  document.getElementById("btn-rerun").disabled = true;
  document.getElementById("btn-change").disabled = true;
  const body = { action };
  if (newsId) body.news_id = newsId;
  try {
    const resp = await fetch(`${API}/runs/${currentRun}/steps/${currentStep}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      setStatus(`操作失败: ${err.detail || resp.status}`);
      isResolving = false;
      document.getElementById("btn-proceed").disabled = false;
      document.getElementById("btn-rerun").disabled = false;
      document.getElementById("btn-change").disabled = false;
      return;
    }
    isResolving = false;
  } catch (e) {
    setStatus(`网络错误: ${e.message}`);
    isResolving = false;
    document.getElementById("btn-proceed").disabled = false;
    document.getElementById("btn-rerun").disabled = false;
    document.getElementById("btn-change").disabled = false;
  }
}



document.getElementById("btn-proceed").addEventListener("click", () => {

  if (currentStep === 0) {

    if (!selectedNewsId) {

      setStatus("请先选择一条新闻");

      return;

    }

    resolve("proceed", selectedNewsId);

    return;

  }

  resolve("proceed");

});

document.getElementById("btn-rerun").addEventListener("click", () => resolve("rerun"));

document.getElementById("btn-change").addEventListener("click", () => resolve("change_direction"));



createRun();

