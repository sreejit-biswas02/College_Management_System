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
  formatDayOfWeek,
  formatIndianDate,
  formatIndianDateTime,
  formatNoticeAudience,
  formatOfferingLabel,
  formatTime12h,
  renderEmptyState,
  renderErrorState,
  renderLoading,
  renderStatusBadge,
} from "../components/ui.js";

function openFormModal({ title, fieldsHtml, submitLabel = "Save", onSubmit }) {
  openModal({
    title,
    bodyHtml: `<form id="faculty-modal-form">${fieldsHtml}<button class="btn btn-primary btn-block" type="submit">${escapeHtml(submitLabel)}</button></form>`,
  });
  const formEl = document.getElementById("faculty-modal-form");
  formEl?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = formEl.querySelector('button[type="submit"]');
    const orig = btn ? btn.textContent : submitLabel;
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Saving...";
    }
    try {
      const formData = new FormData(formEl);
      await onSubmit(Object.fromEntries(formData.entries()));
      closeModal();
    } catch (err) {
      showToast(err.message || "Operation failed.", "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = orig;
      }
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

  const offeringItems = offerings.items || [];
  const offeringSlice = offeringItems.slice(0, 8);

  const [enrollmentCounts, assignmentLists, sessionLists] = await Promise.all([
    Promise.all(
      offeringSlice.map((o) =>
        opsApi
          .listOfferingEnrollments(o.id, { page: 1, page_size: 1 })
          .then((res) => res.total || 0)
          .catch(() => 0)
      )
    ),
    Promise.all(
      offeringSlice.map((o) =>
        opsApi
          .listOfferingAssignments(o.id, { page: 1, page_size: 10 })
          .then((res) => res.items || [])
          .catch(() => [])
      )
    ),
    Promise.all(
      offeringSlice.map((o) =>
        opsApi
          .listOfferingSessions(o.id, { page: 1, page_size: 5 })
          .then((res) =>
            (res.items || []).map((s) => ({ ...s, _offering: o }))
          )
          .catch(() => [])
      )
    ),
  ]);

  const totalEnrolled = enrollmentCounts.reduce((acc, n) => acc + n, 0);
  const allAssignments = assignmentLists
    .flat()
    .sort((a, b) => new Date(a.due_at) - new Date(b.due_at));

  const submissionCounts = await Promise.all(
    allAssignments.slice(0, 8).map((asg) =>
      opsApi
        .listAssignmentSubmissions(asg.id, { page: 1, page_size: 50 })
        .then((res) => ({
          id: asg.id,
          total: res.total || 0,
          pending: (res.items || []).filter(
            (s) => s.score === null || s.score === undefined
          ).length,
        }))
        .catch(() => ({ id: asg.id, total: 0, pending: 0 }))
    )
  );
  const subStatsByAsg = new Map(submissionCounts.map((s) => [s.id, s]));
  const totalPendingSubs = submissionCounts.reduce((acc, s) => acc + s.pending, 0);

  const recentSessions = sessionLists
    .flat()
    .sort((a, b) => String(b.session_date).localeCompare(String(a.session_date)))
    .slice(0, 5);

  container.innerHTML = `
    <section class="card" style="margin-bottom:1.25rem;">
      <div class="card-header" style="margin-bottom:0.5rem;">
        <div>
          <h2 class="card-title">${escapeHtml(profile.user.full_name)}</h2>
          <p class="text-muted" style="font-size:0.875rem;">
            ${escapeHtml(profile.employee_id)} &bull;
            ${escapeHtml(profile.designation)} &bull;
            ${escapeHtml(`${profile.department.code} — ${profile.department.name}`)}
          </p>
        </div>
        ${renderStatusBadge(profile.user.is_active ? "Active" : "Inactive", profile.user.is_active ? "success" : "danger")}
      </div>
    </section>

    <section class="stats-grid">
      <div class="stat-card">
        <div class="text-muted">Assigned Offerings</div>
        <div class="stat-value">${escapeHtml(offerings.total)}</div>
        <div class="stat-subtext">Active teaching courses</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Enrolled Students</div>
        <div class="stat-value">${escapeHtml(totalEnrolled)}</div>
        <div class="stat-subtext">Across assigned offerings</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Pending Evaluations</div>
        <div class="stat-value">${escapeHtml(totalPendingSubs)}</div>
        <div class="stat-subtext">Ungraded submissions</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Weekly Classes</div>
        <div class="stat-value">${escapeHtml(timetable.length)}</div>
        <div class="stat-subtext">Scheduled slots</div>
      </div>
    </section>

    <div class="dashboard-grid">
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
          rows: offeringItems,
          emptyTitle: "No assigned course offerings",
          emptyDescription: "You have not been assigned to any offerings yet.",
        })}
      </section>

      <section class="card">
        <div class="card-header"><h2 class="card-title">Assignments &amp; Pending Grading</h2></div>
        ${renderDataTable({
          columns: [
            { key: "title", label: "Assignment" },
            {
              label: "Course",
              render: (r) =>
                escapeHtml(
                  r.course_offering?.course
                    ? `${r.course_offering.course.code} (${r.course_offering.section})`
                    : "—"
                ),
            },
            { label: "Due", render: (r) => escapeHtml(formatIndianDateTime(r.due_at)) },
            {
              label: "Pending",
              render: (r) => {
                const st = subStatsByAsg.get(r.id);
                if (!st) return '<span class="text-muted">—</span>';
                return st.pending > 0
                  ? renderStatusBadge(`${st.pending} to grade`, "warning")
                  : renderStatusBadge(`${st.total} graded`, "success");
              },
            },
          ],
          rows: allAssignments.slice(0, 6),
          emptyTitle: "No assignments published",
        })}
      </section>
    </div>

    <div class="dashboard-grid">
      <section class="card">
        <div class="card-header"><h2 class="card-title">Recent Attendance Sessions</h2></div>
        ${renderDataTable({
          columns: [
            {
              label: "Course",
              render: (r) => escapeHtml(formatOfferingLabel(r._offering)),
            },
            {
              label: "Date",
              render: (r) =>
                escapeHtml(`${formatIndianDate(r.session_date)} (#${r.session_number})`),
            },
            { key: "topic", label: "Topic" },
            { label: "Marked", render: (r) => escapeHtml(r.records?.length ?? 0) },
          ],
          rows: recentSessions,
          emptyTitle: "No attendance sessions recorded",
        })}
      </section>

      <section class="card">
        <div class="card-header"><h2 class="card-title">Weekly Timetable</h2></div>
        ${renderDataTable({
          columns: [
            { label: "Day", render: (r) => escapeHtml(formatDayOfWeek(r.day_of_week)) },
            {
              label: "Time",
              render: (r) =>
                escapeHtml(`${formatTime12h(r.start_time)} – ${formatTime12h(r.end_time)}`),
            },
            {
              label: "Course",
              render: (r) => escapeHtml(formatOfferingLabel(r.course_offering)),
            },
            { label: "Room", render: (r) => escapeHtml(r.room || "TBA") },
          ],
          rows: timetable.slice(0, 6),
          emptyTitle: "No timetable slots scheduled",
        })}
      </section>
    </div>

    <section class="card" style="margin-top:1.25rem;">
      <div class="card-header"><h2 class="card-title">Recent Notices</h2></div>
      ${renderDataTable({
        columns: [
          { key: "title", label: "Title" },
          { label: "Audience", render: (r) => escapeHtml(formatNoticeAudience(r)) },
          { label: "Published", render: (r) => escapeHtml(formatIndianDateTime(r.published_at)) },
        ],
        rows: notices.items,
        emptyTitle: "No notices available",
      })}
    </section>
  `;
}

async function renderFacultyProfile(container) {
  const profile = await opsApi.getMyFacultyProfile();
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">My Faculty Profile</h2>
        ${renderStatusBadge(profile.user.is_active ? "Active" : "Inactive", profile.user.is_active ? "success" : "danger")}
      </div>
      <div class="profile-grid">
        <div class="profile-field">
          <div class="profile-field-label">Full Name</div>
          <strong>${escapeHtml(profile.user.full_name)}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Email</div>
          <strong>${escapeHtml(profile.user.email)}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Faculty ID</div>
          <strong>${escapeHtml(profile.employee_id)}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Designation</div>
          <strong>${escapeHtml(profile.designation)}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Department</div>
          <strong>${escapeHtml(`${profile.department.code} — ${profile.department.name}`)}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Joining Date</div>
          <strong>${escapeHtml(profile.joining_date ? formatIndianDate(profile.joining_date) : "Not provided")}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Phone</div>
          <strong>${escapeHtml(profile.phone || "Not provided")}</strong>
        </div>
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
          {
            label: "Course",
            render: (r) => escapeHtml(`${r.course.code} — ${r.course.title}`),
          },
          {
            label: "Semester",
            render: (r) => escapeHtml(`${r.semester.name} (${r.semester.academic_year})`),
          },
          { key: "section", label: "Section" },
          {
            label: "Capacity",
            render: (r) => escapeHtml(r.max_capacity ?? "Unlimited"),
          },
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
        <h2 class="card-title">Offering Students</h2>
        <select id="fac-offering-select" class="form-control" style="max-width:360px;" aria-label="Select course offering">
          ${offerings.items
            .map(
              (o) =>
                `<option value="${o.id}">${escapeHtml(`${formatOfferingLabel(o)} • ${o.semester.name}`)}</option>`
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
    try {
      const data = await opsApi.listOfferingEnrollments(select.value, { page: 1, page_size: 100 });
      tableEl.innerHTML = renderDataTable({
        columns: [
          { label: "Student ID", render: (r) => escapeHtml(r.student.roll_number) },
          { label: "Name", render: (r) => escapeHtml(r.student.user.full_name) },
          { label: "Email", render: (r) => escapeHtml(r.student.user.email) },
          {
            label: "Department",
            render: (r) =>
              escapeHtml(`${r.student.department.code} — ${r.student.department.name}`),
          },
          {
            label: "Semester",
            render: (r) => escapeHtml(`Semester ${r.student.current_semester_number}`),
          },
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
    } catch (err) {
      tableEl.innerHTML = renderErrorState(err.message || "Failed to load enrolled students.");
    }
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
          <select id="att-offering-select" class="form-control" style="max-width:340px;" aria-label="Select course offering">
            ${offerings.items
              .map(
                (o) =>
                  `<option value="${o.id}">${escapeHtml(formatOfferingLabel(o))}</option>`
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
    let data;
    try {
      data = await opsApi.listOfferingSessions(select.value, { page: 1, page_size: 20 });
    } catch (err) {
      listEl.innerHTML = renderErrorState(err.message || "Failed to load attendance sessions.");
      return;
    }
    const sessionsById = new Map(data.items.map((s) => [String(s.id), s]));
    listEl.innerHTML = renderDataTable({
      columns: [
        {
          label: "Date",
          render: (r) => escapeHtml(formatIndianDate(r.session_date)),
        },
        { label: "Session", render: (r) => escapeHtml(`Session #${r.session_number}`) },
        { key: "topic", label: "Topic" },
        { label: "Marked", render: (r) => escapeHtml(`${r.records.length} student(s)`) },
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
        const session = sessionsById.get(String(sessionId));
        const existingStatusByStudent = new Map(
          (session?.records || []).map((rec) => [rec.student_id, rec.status])
        );
        btn.disabled = true;
        let enrolled;
        try {
          enrolled = await opsApi.listOfferingEnrollments(select.value, {
            page: 1,
            page_size: 100,
          });
        } catch (err) {
          showToast(err.message || "Failed to load enrolled students.", "error");
          btn.disabled = false;
          return;
        }
        btn.disabled = false;
        const activeStudents = enrolled.items.filter((e) => e.status === "enrolled");
        if (!activeStudents.length) {
          showToast("No actively enrolled students in this offering.", "error");
          return;
        }
        const rowsHtml = activeStudents
          .map((e) => {
            const currentStatus = existingStatusByStudent.get(e.student.id) || "present";
            return `
            <div style="display:flex;align-items:center;justify-content:space-between;gap:0.75rem;margin-bottom:0.5rem;">
              <span>${escapeHtml(`${e.student.roll_number} — ${e.student.user.full_name}`)}</span>
              <select class="form-control att-status-sel" data-student-id="${e.student.id}" style="max-width:140px;">
                <option value="present" ${currentStatus === "present" ? "selected" : ""}>Present</option>
                <option value="absent" ${currentStatus === "absent" ? "selected" : ""}>Absent</option>
                <option value="late" ${currentStatus === "late" ? "selected" : ""}>Late</option>
                <option value="excused" ${currentStatus === "excused" ? "selected" : ""}>Excused</option>
              </select>
            </div>`;
          })
          .join("");

        openModal({
          title: `Mark Attendance — ${formatIndianDate(session?.session_date)} (Session #${session?.session_number ?? sessionId})`,
          bodyHtml: `<form id="bulk-att-form">${rowsHtml}<button class="btn btn-primary btn-block" type="submit" style="margin-top:1rem;">Save Attendance</button></form>`,
        });
        const attForm = document.getElementById("bulk-att-form");
        attForm?.addEventListener("submit", async (ev) => {
          ev.preventDefault();
          const submitBtn = attForm.querySelector('button[type="submit"]');
          if (submitBtn) submitBtn.disabled = true;
          try {
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
          } catch (err) {
            showToast(err.message || "Failed to save attendance.", "error");
          } finally {
            if (submitBtn) submitBtn.disabled = false;
          }
        });
      });
    });
  }

  document.getElementById("new-att-session-btn")?.addEventListener("click", () => {
    const today = new Date().toISOString().slice(0, 10);
    openFormModal({
      title: "Create Attendance Session",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Session Date <span class="required-star">*</span></label><input name="session_date" type="date" value="${today}" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Session Number <span class="required-star">*</span></label><input name="session_number" type="number" min="1" value="1" class="form-control" required /></div>
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
          <select id="asg-offering-select" class="form-control" style="max-width:340px;" aria-label="Select course offering">
            ${offerings.items
              .map(
                (o) =>
                  `<option value="${o.id}">${escapeHtml(formatOfferingLabel(o))}</option>`
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

  async function loadSubmissions(assignment) {
    subEl.innerHTML = renderLoading("Loading submissions...");
    let subs;
    try {
      subs = await opsApi.listAssignmentSubmissions(assignment.id, {
        page: 1,
        page_size: 50,
      });
    } catch (err) {
      subEl.innerHTML = renderErrorState(err.message || "Failed to load submissions.");
      return;
    }
    const courseLabel = assignment.course_offering?.course
      ? ` — ${assignment.course_offering.course.code} (${assignment.course_offering.section})`
      : "";
    subEl.innerHTML = `
      <h3 class="card-title" style="margin-bottom:0.75rem;">
        Submissions: ${escapeHtml(assignment.title)}${escapeHtml(courseLabel)}
      </h3>
      ${renderDataTable({
        columns: [
          {
            label: "Student",
            render: (r) =>
              r.student
                ? escapeHtml(`${r.student.roll_number} — ${r.student.user.full_name}`)
                : escapeHtml(`Student #${r.student_id}`),
          },
          {
            label: "Submitted",
            render: (r) => escapeHtml(formatIndianDateTime(r.submitted_at)),
          },
          { key: "content", label: "Content" },
          {
            label: "Attachments",
            render: (r) =>
              renderFileListHtml(r.attachments || [], { compact: true }),
          },
          {
            label: "Score",
            render: (r) =>
              r.score !== null && r.score !== undefined
                ? renderStatusBadge(`${r.score} / ${assignment.max_score}`, "success")
                : renderStatusBadge("Pending", "warning"),
          },
          { key: "feedback", label: "Feedback" },
          {
            label: "Action",
            render: (r) =>
              `<button class="btn btn-primary btn-sm grade-sub-btn" data-id="${r.id}" type="button">${
                r.score !== null && r.score !== undefined ? "Update Grade" : "Grade"
              }</button>`,
          },
        ],
        rows: subs.items,
        emptyTitle: "No submissions yet",
      })}
    `;
    bindFileListActions(subEl);
    subEl.querySelectorAll(".grade-sub-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const sub = subs.items.find((item) => String(item.id) === btn.dataset.id);
        const studentLabel = sub?.student
          ? `${sub.student.roll_number} — ${sub.student.user.full_name}`
          : `Submission #${btn.dataset.id}`;
        openFormModal({
          title: `Grade: ${studentLabel}`,
          submitLabel: "Save Grade",
          fieldsHtml: `
            <div class="form-group">
              <label class="form-label">Score (Max: ${escapeHtml(assignment.max_score)}) <span class="required-star">*</span></label>
              <input name="score" type="number" step="0.5" min="0" max="${escapeHtml(assignment.max_score)}" value="${escapeHtml(sub?.score ?? "")}" class="form-control" required />
            </div>
            <div class="form-group">
              <label class="form-label">Feedback</label>
              <textarea name="feedback" rows="3" class="form-control" placeholder="Optional feedback for the student...">${escapeHtml(sub?.feedback || "")}</textarea>
            </div>
          `,
          onSubmit: async (form) => {
            await opsApi.gradeSubmission(btn.dataset.id, {
              score: Number(form.score),
              feedback: form.feedback || null,
            });
            showToast("Submission graded.", "success");
            loadSubmissions(assignment);
          },
        });
      });
    });
  }

  async function load() {
    asgEl.innerHTML = renderLoading();
    subEl.innerHTML = "";
    let data;
    try {
      data = await opsApi.listOfferingAssignments(select.value, {
        page: 1,
        page_size: 20,
      });
    } catch (err) {
      asgEl.innerHTML = renderErrorState(err.message || "Failed to load assignments.");
      return;
    }
    const asgById = new Map(data.items.map((a) => [String(a.id), a]));
    asgEl.innerHTML = renderDataTable({
      columns: [
        { key: "title", label: "Title" },
        {
          label: "Course",
          render: (r) =>
            escapeHtml(
              r.course_offering?.course
                ? `${r.course_offering.course.code} (${r.course_offering.section})`
                : "—"
            ),
        },
        { label: "Due At", render: (r) => escapeHtml(formatIndianDateTime(r.due_at)) },
        { key: "max_score", label: "Max Score" },
        {
          label: "Materials",
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
      btn.addEventListener("click", () => {
        const asg = asgById.get(btn.dataset.id);
        if (asg) loadSubmissions(asg);
      });
    });
    if (showSubmissions && data.items[0]) {
      loadSubmissions(data.items[0]);
    }
  }

  document.getElementById("new-asg-btn")?.addEventListener("click", () => {
    const due = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 16);
    openFormModal({
      title: "Publish Assignment",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Title <span class="required-star">*</span></label><input name="title" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Description</label><textarea name="description" rows="2" class="form-control"></textarea></div>
        <div class="form-group"><label class="form-label">Due Date &amp; Time <span class="required-star">*</span></label><input name="due_at" type="datetime-local" value="${due}" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Max Score <span class="required-star">*</span></label><input name="max_score" type="number" value="100" min="1" class="form-control" required /></div>
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
          { label: "Audience", render: (r) => escapeHtml(formatNoticeAudience(r)) },
          {
            label: "Published By",
            render: (r) => escapeHtml(r.posted_by_user?.full_name || "Administration"),
          },
          {
            label: "Published",
            render: (r) => escapeHtml(formatIndianDateTime(r.published_at)),
          },
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
        emptyTitle: "No notices available",
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
        <div class="form-group"><label class="form-label">Course Offering <span class="required-star">*</span></label>
          <select name="course_offering_id" class="form-control">
            ${offerings.items
              .map(
                (o) =>
                  `<option value="${o.id}">${escapeHtml(formatOfferingLabel(o))}</option>`
              )
              .join("")}
          </select>
        </div>
        <div class="form-group"><label class="form-label">Title <span class="required-star">*</span></label><input name="title" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Body <span class="required-star">*</span></label><textarea name="body" rows="3" class="form-control" required></textarea></div>
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
          { label: "Day", render: (r) => escapeHtml(formatDayOfWeek(r.day_of_week)) },
          {
            label: "Time",
            render: (r) =>
              escapeHtml(`${formatTime12h(r.start_time)} – ${formatTime12h(r.end_time)}`),
          },
          {
            label: "Course",
            render: (r) => escapeHtml(formatOfferingLabel(r.course_offering, "Not assigned")),
          },
          {
            label: "Semester",
            render: (r) =>
              escapeHtml(
                r.course_offering?.semester
                  ? `${r.course_offering.semester.name} (${r.course_offering.semester.academic_year})`
                  : "—"
              ),
          },
          { label: "Room", render: (r) => escapeHtml(r.room || "TBA") },
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
