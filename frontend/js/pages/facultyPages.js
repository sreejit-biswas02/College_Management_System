import * as filesApi from "../api/filesApi.js";
import * as opsApi from "../api/operationsApi.js";
import { renderDataTable } from "../components/dataTable.js";
import {
  ALLOWED_EXTENSIONS,
  bindFileListActions,
  formatBytes,
  renderFileListHtml,
  validateClientFile,
} from "../components/fileUpload.js";
import { closeModal, confirmDialog, openModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import {
  escapeHtml,
  renderEmptyState,
  renderErrorState,
  renderLoading,
  renderStatusBadge,
} from "../components/ui.js";

function openFormModal({ title, fieldsHtml, onSubmit }) {
  openModal({
    title,
    bodyHtml: `<form id="faculty-modal-form">${fieldsHtml}<button class="btn btn-primary btn-block" type="submit">Save</button></form>`,
  });
  const formEl = document.getElementById("faculty-modal-form");
  formEl?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = formEl.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const formData = new FormData(formEl);
      await onSubmit(Object.fromEntries(formData.entries()));
      closeModal();
    } catch (err) {
      showToast(err.message || "Operation failed.", "error");
    } finally {
      btn.disabled = false;
    }
  });
}

async function renderFacultyOverview(container) {
  const [profile, offerings, notices, timetable] = await Promise.all([
    opsApi.getMyFacultyProfile(),
    opsApi.getMyFacultyOfferings({ page: 1, page_size: 20 }),
    opsApi.listNotices({ page: 1, page_size: 5 }),
    opsApi.getMyTimetable(),
  ]);

  container.innerHTML = `
    <section class="stats-grid">
      <div class="stat-card">
        <div class="text-muted">Designation</div>
        <div class="stat-value" style="font-size:1.15rem;">${escapeHtml(profile.designation)}</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Assigned Offerings</div>
        <div class="stat-value">${escapeHtml(offerings.total)}</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Weekly Classes</div>
        <div class="stat-value">${escapeHtml(timetable.length)}</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Relevant Notices</div>
        <div class="stat-value">${escapeHtml(notices.total)}</div>
      </div>
    </section>

    <section class="card">
      <div class="card-header"><h2 class="card-title">My Assigned Course Offerings</h2></div>
      ${renderDataTable({
        columns: [
          { label: "Course", render: (r) => escapeHtml(`${r.course.code} — ${r.course.title}`) },
          { label: "Semester", render: (r) => escapeHtml(`${r.semester.name} (${r.semester.academic_year})`) },
          { key: "section", label: "Section" },
          {
            label: "Status",
            render: (r) =>
              renderStatusBadge(
                r.is_active ? "Active" : "Inactive",
                r.is_active ? "success" : "danger"
              ),
          },
        ],
        rows: offerings.items,
        emptyTitle: "No assigned course offerings",
        emptyDescription: "You have not been assigned to any offerings yet.",
      })}
    </section>
  `;
}

async function renderFacultyProfile(container) {
  const profile = await opsApi.getMyFacultyProfile();
  container.innerHTML = `
    <section class="card">
      <div class="card-header"><h2 class="card-title">My Faculty Profile</h2></div>
      <div class="form-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;">
        <div><div class="text-muted">Full Name</div><strong>${escapeHtml(profile.user.full_name)}</strong></div>
        <div><div class="text-muted">Email</div><strong>${escapeHtml(profile.user.email)}</strong></div>
        <div><div class="text-muted">Employee ID</div><strong>${escapeHtml(profile.employee_id)}</strong></div>
        <div><div class="text-muted">Designation</div><strong>${escapeHtml(profile.designation)}</strong></div>
        <div><div class="text-muted">Department</div><strong>${escapeHtml(`${profile.department.code} — ${profile.department.name}`)}</strong></div>
        <div><div class="text-muted">Joining Date</div><strong>${escapeHtml(profile.joining_date || "—")}</strong></div>
      </div>
    </section>
  `;
}

async function renderFacultyOfferings(container) {
  const offerings = await opsApi.getMyFacultyOfferings({ page: 1, page_size: 50 });
  container.innerHTML = `
    <section class="card">
      <div class="card-header"><h2 class="card-title">My Course Offerings</h2></div>
      ${renderDataTable({
        columns: [
          { key: "id", label: "Offering ID" },
          { label: "Code", render: (r) => escapeHtml(r.course.code) },
          { label: "Title", render: (r) => escapeHtml(r.course.title) },
          { label: "Semester", render: (r) => escapeHtml(`${r.semester.name} (${r.semester.academic_year})`) },
          { key: "section", label: "Section" },
          { key: "max_capacity", label: "Capacity" },
        ],
        rows: offerings.items,
      })}
    </section>
  `;
}

async function renderFacultyStudents(container) {
  const offerings = await opsApi.getMyFacultyOfferings({ page: 1, page_size: 50 });
  if (!offerings.items.length) {
    container.innerHTML = `<section class="card">${renderEmptyState("No assigned offerings")}</section>`;
    return;
  }

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">Enrolled Students</h2>
        <select id="fac-offering-select" class="form-control" style="max-width:320px;">
          ${offerings.items
            .map(
              (o) =>
                `<option value="${o.id}">${escapeHtml(`${o.course.code} (${o.section}) — ${o.semester.name}`)}</option>`
            )
            .join("")}
        </select>
      </div>
      <div id="fac-students-table"></div>
    </section>
  `;

  const select = document.getElementById("fac-offering-select");
  const tableEl = document.getElementById("fac-students-table");

  async function load() {
    tableEl.innerHTML = renderLoading();
    const data = await opsApi.listOfferingEnrollments(select.value, { page: 1, page_size: 100 });
    tableEl.innerHTML = renderDataTable({
      columns: [
        { label: "Roll No", render: (r) => escapeHtml(r.student.roll_number) },
        { label: "Name", render: (r) => escapeHtml(r.student.user.full_name) },
        { label: "Email", render: (r) => escapeHtml(r.student.user.email) },
        {
          label: "Status",
          render: (r) =>
            renderStatusBadge(
              r.status,
              r.status === "enrolled" ? "success" : "warning"
            ),
        },
      ],
      rows: data.items,
      emptyTitle: "No students enrolled",
    });
  }

  select.addEventListener("change", load);
  await load();
}

async function renderFacultyAttendance(container) {
  const offerings = await opsApi.getMyFacultyOfferings({ page: 1, page_size: 50 });
  if (!offerings.items.length) {
    container.innerHTML = `<section class="card">${renderEmptyState("No assigned offerings")}</section>`;
    return;
  }

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">Attendance Management</h2>
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap;">
          <select id="att-offering-select" class="form-control" style="max-width:280px;">
            ${offerings.items
              .map(
                (o) =>
                  `<option value="${o.id}">${escapeHtml(`${o.course.code} (${o.section})`)}</option>`
              )
              .join("")}
          </select>
          <button id="new-att-session-btn" class="btn btn-primary btn-sm" type="button">+ New Session</button>
        </div>
      </div>
      <div id="att-sessions-list"></div>
    </section>
  `;

  const select = document.getElementById("att-offering-select");
  const listEl = document.getElementById("att-sessions-list");

  async function load() {
    listEl.innerHTML = renderLoading();
    const data = await opsApi.listOfferingSessions(select.value, { page: 1, page_size: 20 });
    listEl.innerHTML = renderDataTable({
      columns: [
        { key: "id", label: "ID" },
        { key: "session_date", label: "Date" },
        { key: "session_number", label: "#" },
        { key: "topic", label: "Topic" },
        { label: "Marked", render: (r) => escapeHtml(r.records.length) },
        {
          label: "Action",
          render: (r) =>
            `<button class="btn btn-outline btn-sm mark-att-btn" data-id="${r.id}" type="button">Mark Attendance</button>`,
        },
      ],
      rows: data.items,
      emptyTitle: "No attendance sessions yet",
    });

    listEl.querySelectorAll(".mark-att-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sessionId = btn.dataset.id;
        const enrolled = await opsApi.listOfferingEnrollments(select.value, {
          page: 1,
          page_size: 100,
        });
        const activeStudents = enrolled.items.filter((e) => e.status === "enrolled");
        if (!activeStudents.length) {
          showToast("No actively enrolled students in this offering.", "error");
          return;
        }
        const rowsHtml = activeStudents
          .map(
            (e) => `
            <div style="display:flex;align-items:center;justify-content:space-between;gap:0.75rem;margin-bottom:0.5rem;">
              <span>${escapeHtml(`${e.student.roll_number} — ${e.student.user.full_name}`)}</span>
              <select class="form-control att-status-sel" data-student-id="${e.student.id}" style="max-width:140px;">
                <option value="present">Present</option>
                <option value="absent">Absent</option>
                <option value="late">Late</option>
                <option value="excused">Excused</option>
              </select>
            </div>`
          )
          .join("");

        openModal({
          title: `Mark Attendance (Session #${sessionId})`,
          bodyHtml: `<form id="bulk-att-form">${rowsHtml}<button class="btn btn-primary btn-block" type="submit" style="margin-top:1rem;">Save Attendance</button></form>`,
        });
        document.getElementById("bulk-att-form")?.addEventListener("submit", async (ev) => {
          ev.preventDefault();
          const records = Array.from(document.querySelectorAll(".att-status-sel")).map(
            (sel) => ({
              student_id: Number(sel.dataset.studentId),
              status: sel.value,
            })
          );
          await opsApi.markAttendanceRecords(sessionId, records);
          closeModal();
          showToast("Attendance saved.", "success");
          load();
        });
      });
    });
  }

  document.getElementById("new-att-session-btn")?.addEventListener("click", () => {
    const today = new Date().toISOString().slice(0, 10);
    openFormModal({
      title: "Create Attendance Session",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Session Date</label><input name="session_date" type="date" value="${today}" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Session Number</label><input name="session_number" type="number" min="1" value="1" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Topic</label><input name="topic" class="form-control" placeholder="Lecture topic" /></div>
      `,
      onSubmit: async (form) => {
        await opsApi.createAttendanceSession({
          course_offering_id: Number(select.value),
          session_date: form.session_date,
          session_number: Number(form.session_number),
          topic: form.topic || null,
        });
        showToast("Attendance session created.", "success");
        load();
      },
    });
  });

  select.addEventListener("change", load);
  await load();
}

async function renderFacultyAssignments(container, showSubmissions = false) {
  const offerings = await opsApi.getMyFacultyOfferings({ page: 1, page_size: 50 });
  if (!offerings.items.length) {
    container.innerHTML = `<section class="card">${renderEmptyState("No assigned offerings")}</section>`;
    return;
  }

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">${showSubmissions ? "Submission Evaluation" : "Assignments"}</h2>
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap;">
          <select id="asg-offering-select" class="form-control" style="max-width:280px;">
            ${offerings.items
              .map(
                (o) =>
                  `<option value="${o.id}">${escapeHtml(`${o.course.code} (${o.section})`)}</option>`
              )
              .join("")}
          </select>
          ${
            !showSubmissions
              ? '<button id="new-asg-btn" class="btn btn-primary btn-sm" type="button">+ New Assignment</button>'
              : ""
          }
        </div>
      </div>
      <div id="asg-list"></div>
      <div id="sub-list" style="margin-top:1.25rem;"></div>
    </section>
  `;

  const select = document.getElementById("asg-offering-select");
  const asgEl = document.getElementById("asg-list");
  const subEl = document.getElementById("sub-list");

  async function loadSubmissions(assignmentId) {
    subEl.innerHTML = renderLoading("Loading submissions...");
    const subs = await opsApi.listAssignmentSubmissions(assignmentId, {
      page: 1,
      page_size: 50,
    });
    subEl.innerHTML = `
      <h3 class="card-title" style="margin-bottom:0.75rem;">Submissions (Assignment #${escapeHtml(assignmentId)})</h3>
      ${renderDataTable({
        columns: [
          { key: "id", label: "ID" },
          { key: "student_id", label: "Student ID" },
          { key: "content", label: "Content" },
          { key: "score", label: "Score" },
          { key: "feedback", label: "Feedback" },
          {
            label: "Action",
            render: (r) =>
              `<button class="btn btn-primary btn-sm grade-sub-btn" data-id="${r.id}" type="button">Grade</button>`,
          },
        ],
        rows: subs.items,
        emptyTitle: "No submissions yet",
      })}
    `;
    subEl.querySelectorAll(".grade-sub-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        openFormModal({
          title: `Grade Submission #${btn.dataset.id}`,
          fieldsHtml: `
            <div class="form-group"><label class="form-label">Score</label><input name="score" type="number" step="0.5" min="0" class="form-control" required /></div>
            <div class="form-group"><label class="form-label">Feedback</label><textarea name="feedback" rows="3" class="form-control"></textarea></div>
          `,
          onSubmit: async (form) => {
            await opsApi.gradeSubmission(btn.dataset.id, {
              score: Number(form.score),
              feedback: form.feedback || null,
            });
            showToast("Submission graded.", "success");
            loadSubmissions(assignmentId);
          },
        });
      });
    });
  }

  async function load() {
    asgEl.innerHTML = renderLoading();
    subEl.innerHTML = "";
    const data = await opsApi.listOfferingAssignments(select.value, {
      page: 1,
      page_size: 20,
    });
    asgEl.innerHTML = renderDataTable({
      columns: [
        { key: "id", label: "ID" },
        { key: "title", label: "Title" },
        { key: "due_at", label: "Due At" },
        { key: "max_score", label: "Max Score" },
        {
          label: "Attachments",
          render: (r) =>
            `<button class="btn btn-outline btn-sm manage-files-btn" data-id="${r.id}" data-title="${escapeHtml(r.title)}" type="button">Files</button>`,
        },
        {
          label: "Submissions",
          render: (r) =>
            `<button class="btn btn-outline btn-sm view-subs-btn" data-id="${r.id}" type="button">View Submissions</button>`,
        },
      ],
      rows: data.items,
      emptyTitle: "No assignments published",
    });

    asgEl.querySelectorAll(".manage-files-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const assignmentId = btn.dataset.id;
        async function openAttachmentsModal() {
          const files = await filesApi.listAssignmentAttachments(assignmentId);
          openModal({
            title: `Attachments: ${btn.dataset.title}`,
            bodyHtml: `
              <form id="fac-attach-form" style="margin-bottom:1rem;">
                <div class="form-group">
                  <label class="form-label">Upload Attachment (max 20 MB)</label>
                  <input id="fac-file-input" type="file" accept="${ALLOWED_EXTENSIONS.join(",")}" class="form-control" required />
                  <span id="fac-file-info" class="text-muted"></span>
                </div>
                <div id="fac-upload-progress" class="text-muted hidden"></div>
                <button id="fac-upload-btn" class="btn btn-primary btn-sm" type="submit">Upload File</button>
              </form>
              <div id="fac-files-list">${renderFileListHtml(files, { canDelete: true })}</div>
            `,
          });
          const fileInput = document.getElementById("fac-file-input");
          const fileInfo = document.getElementById("fac-file-info");
          const progEl = document.getElementById("fac-upload-progress");
          fileInput?.addEventListener("change", () => {
            const f = fileInput.files[0];
            fileInfo.textContent = f ? `${f.name} (${formatBytes(f.size)})` : "";
          });
          document.getElementById("fac-attach-form")?.addEventListener("submit", async (e) => {
            e.preventDefault();
            const f = fileInput.files[0];
            const err = validateClientFile(f, 20 * 1024 * 1024);
            if (err) {
              showToast(err, "error");
              return;
            }
            const upBtn = document.getElementById("fac-upload-btn");
            upBtn.disabled = true;
            progEl.classList.remove("hidden");
            try {
              const fd = new FormData();
              fd.append("file", f);
              await filesApi.uploadAssignmentAttachment(assignmentId, fd, (pct) => {
                progEl.textContent = `Uploading: ${pct}%`;
              });
              showToast("Attachment uploaded.", "success");
              await openAttachmentsModal();
            } catch (uploadErr) {
              showToast(uploadErr.message || "Upload failed.", "error");
              upBtn.disabled = false;
            }
          });
          bindFileListActions(document.getElementById("fac-files-list"), {
            onDeleted: openAttachmentsModal,
          });
        }
        await openAttachmentsModal();
      });
    });

    asgEl.querySelectorAll(".view-subs-btn").forEach((btn) => {
      btn.addEventListener("click", () => loadSubmissions(btn.dataset.id));
    });
    if (showSubmissions && data.items[0]) {
      loadSubmissions(data.items[0].id);
    }
  }

  document.getElementById("new-asg-btn")?.addEventListener("click", () => {
    const due = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 16);
    openFormModal({
      title: "Publish Assignment",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Title</label><input name="title" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Description</label><textarea name="description" rows="2" class="form-control"></textarea></div>
        <div class="form-group"><label class="form-label">Due Date &amp; Time</label><input name="due_at" type="datetime-local" value="${due}" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Max Score</label><input name="max_score" type="number" value="100" min="1" class="form-control" required /></div>
      `,
      onSubmit: async (form) => {
        await opsApi.createAssignment({
          course_offering_id: Number(select.value),
          title: form.title,
          description: form.description || null,
          due_at: new Date(form.due_at).toISOString(),
          max_score: Number(form.max_score),
        });
        showToast("Assignment published.", "success");
        load();
      },
    });
  });

  select.addEventListener("change", load);
  await load();
}

async function renderFacultyNotices(container) {
  const [notices, offerings] = await Promise.all([
    opsApi.listNotices({ page: 1, page_size: 20 }),
    opsApi.getMyFacultyOfferings({ page: 1, page_size: 50 }),
  ]);

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">Notices</h2>
        ${
          offerings.items.length
            ? '<button id="fac-add-notice-btn" class="btn btn-primary btn-sm" type="button">+ Post Course Notice</button>'
            : ""
        }
      </div>
      ${renderDataTable({
        columns: [
          { key: "title", label: "Title" },
          { key: "body", label: "Message" },
          {
            label: "Status",
            render: (r) =>
              renderStatusBadge(
                r.is_published ? "Published" : "Archived",
                r.is_published ? "success" : "warning"
              ),
          },
          {
            label: "Action",
            render: (r) =>
              r.is_published
                ? `<button class="btn btn-outline btn-sm deact-btn" data-id="${r.id}" type="button">Deactivate</button>`
                : "—",
          },
        ],
        rows: notices.items,
      })}
    </section>
  `;

  container.querySelectorAll(".deact-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      confirmDialog({
        title: "Deactivate Notice",
        message: "Are you sure you want to unpublish this notice?",
        onConfirm: async () => {
          try {
            await opsApi.deactivateNotice(btn.dataset.id);
            showToast("Notice deactivated.", "success");
            renderFacultyNotices(container);
          } catch (err) {
            showToast(err.message || "Unable to deactivate notice.", "error");
          }
        },
      });
    });
  });

  document.getElementById("fac-add-notice-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Publish Course Notice",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Course Offering</label>
          <select name="course_offering_id" class="form-control">
            ${offerings.items
              .map(
                (o) =>
                  `<option value="${o.id}">${escapeHtml(`${o.course.code} (${o.section})`)}</option>`
              )
              .join("")}
          </select>
        </div>
        <div class="form-group"><label class="form-label">Title</label><input name="title" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Body</label><textarea name="body" rows="3" class="form-control" required></textarea></div>
      `,
      onSubmit: async (form) => {
        await opsApi.createNotice({
          title: form.title,
          body: form.body,
          targets: [{ course_offering_id: Number(form.course_offering_id) }],
        });
        showToast("Notice published.", "success");
        renderFacultyNotices(container);
      },
    });
  });
}

async function renderFacultyTimetable(container) {
  const slots = await opsApi.getMyTimetable();
  container.innerHTML = `
    <section class="card">
      <div class="card-header"><h2 class="card-title">My Weekly Timetable</h2></div>
      ${renderDataTable({
        columns: [
          { key: "day_of_week", label: "Day" },
          { key: "start_time", label: "Start" },
          { key: "end_time", label: "End" },
          { key: "course_offering_id", label: "Offering ID" },
          { key: "room", label: "Room" },
        ],
        rows: slots,
        emptyTitle: "No timetable slots scheduled",
      })}
    </section>
  `;
}

export async function renderFacultyPage(container, routeId) {
  container.innerHTML = renderLoading("Loading faculty module...");
  try {
    switch (routeId) {
      case "dashboard":
        await renderFacultyOverview(container);
        break;
      case "profile":
        await renderFacultyProfile(container);
        break;
      case "offerings":
        await renderFacultyOfferings(container);
        break;
      case "students":
        await renderFacultyStudents(container);
        break;
      case "attendance":
        await renderFacultyAttendance(container);
        break;
      case "assignments":
        await renderFacultyAssignments(container, false);
        break;
      case "submissions":
        await renderFacultyAssignments(container, true);
        break;
      case "notices":
        await renderFacultyNotices(container);
        break;
      case "timetable":
        await renderFacultyTimetable(container);
        break;
      default:
        await renderFacultyOverview(container);
    }
  } catch (err) {
    container.innerHTML = renderErrorState(err.message || "Failed to load data.");
  }
}
