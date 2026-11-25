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
import { closeModal, openModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import {
  escapeHtml,
  renderEmptyState,
  renderErrorState,
  renderLoading,
  renderStatusBadge,
} from "../components/ui.js";

async function renderStudentOverview(container) {
  const [profile, enrollments, attendance, notices, timetable] =
    await Promise.all([
      opsApi.getMyStudentProfile(),
      opsApi.listMyEnrollments({ page: 1, page_size: 20 }),
      opsApi.getMyAttendance(),
      opsApi.listNotices({ page: 1, page_size: 5 }),
      opsApi.getMyTimetable(),
    ]);

  container.innerHTML = `
    <section class="stats-grid">
      <div class="stat-card">
        <div class="text-muted">Roll Number</div>
        <div class="stat-value" style="font-size:1.15rem;">${escapeHtml(profile.roll_number)}</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Enrolled Courses</div>
        <div class="stat-value">${escapeHtml(enrollments.total)}</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Attendance</div>
        <div class="stat-value">${escapeHtml(attendance.attendance_percentage)}%</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Weekly Classes</div>
        <div class="stat-value">${escapeHtml(timetable.length)}</div>
      </div>
    </section>

    <section class="card">
      <div class="card-header"><h2 class="card-title">Recent Notices</h2></div>
      ${renderDataTable({
        columns: [
          { key: "title", label: "Title" },
          { key: "body", label: "Message" },
        ],
        rows: notices.items,
        emptyTitle: "No notices available",
      })}
    </section>
  `;
}

async function renderStudentProfile(container) {
  const profile = await opsApi.getMyStudentProfile();
  container.innerHTML = `
    <section class="card">
      <div class="card-header"><h2 class="card-title">My Student Profile</h2></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;">
        <div><div class="text-muted">Full Name</div><strong>${escapeHtml(profile.user.full_name)}</strong></div>
        <div><div class="text-muted">Email</div><strong>${escapeHtml(profile.user.email)}</strong></div>
        <div><div class="text-muted">Roll Number</div><strong>${escapeHtml(profile.roll_number)}</strong></div>
        <div><div class="text-muted">Department</div><strong>${escapeHtml(`${profile.department.code} — ${profile.department.name}`)}</strong></div>
        <div><div class="text-muted">Semester</div><strong>Semester ${escapeHtml(profile.current_semester_number)}</strong></div>
        <div><div class="text-muted">Admission Year</div><strong>${escapeHtml(profile.admission_year)}</strong></div>
      </div>
    </section>
  `;
}

async function renderStudentCourses(container) {
  const data = await opsApi.listMyEnrollments({ page: 1, page_size: 50 });
  container.innerHTML = `
    <section class="card">
      <div class="card-header"><h2 class="card-title">My Enrolled Courses</h2></div>
      ${renderDataTable({
        columns: [
          { label: "Code", render: (r) => escapeHtml(r.course_offering.course.code) },
          { label: "Title", render: (r) => escapeHtml(r.course_offering.course.title) },
          { label: "Section", render: (r) => escapeHtml(r.course_offering.section) },
          { label: "Faculty", render: (r) => escapeHtml(r.course_offering.faculty.user.full_name) },
          { label: "Semester", render: (r) => escapeHtml(r.course_offering.semester.name) },
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
        emptyTitle: "Not enrolled in any courses",
      })}
    </section>
  `;
}

async function renderStudentAttendance(container) {
  const summary = await opsApi.getMyAttendance();
  container.innerHTML = `
    <section class="stats-grid">
      <div class="stat-card"><div class="text-muted">Attendance %</div><div class="stat-value">${escapeHtml(summary.attendance_percentage)}%</div></div>
      <div class="stat-card"><div class="text-muted">Total Sessions</div><div class="stat-value">${escapeHtml(summary.total_sessions)}</div></div>
      <div class="stat-card"><div class="text-muted">Present</div><div class="stat-value">${escapeHtml(summary.present)}</div></div>
      <div class="stat-card"><div class="text-muted">Absent</div><div class="stat-value">${escapeHtml(summary.absent)}</div></div>
    </section>
    <section class="card">
      <div class="card-header"><h2 class="card-title">Attendance History</h2></div>
      ${renderDataTable({
        columns: [
          { key: "session_id", label: "Session ID" },
          {
            label: "Status",
            render: (r) =>
              renderStatusBadge(
                r.status,
                r.status === "present"
                  ? "success"
                  : r.status === "absent"
                    ? "danger"
                    : "warning"
              ),
          },
          { key: "remarks", label: "Remarks" },
          { key: "marked_at", label: "Marked At" },
        ],
        rows: summary.records,
        emptyTitle: "No attendance records yet",
      })}
    </section>
  `;
}

async function renderStudentAssignments(container) {
  const enrollments = await opsApi.listMyEnrollments({
    status: "enrolled",
    page: 1,
    page_size: 50,
  });
  if (!enrollments.items.length) {
    container.innerHTML = `<section class="card">${renderEmptyState("No enrolled courses")}</section>`;
    return;
  }

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">My Assignments</h2>
        <select id="stu-offering-select" class="form-control" style="max-width:300px;">
          ${enrollments.items
            .map(
              (e) =>
                `<option value="${e.course_offering.id}">${escapeHtml(`${e.course_offering.course.code} (${e.course_offering.section})`)}</option>`
            )
            .join("")}
        </select>
      </div>
      <div id="stu-assignments-table"></div>
    </section>
  `;

  const select = document.getElementById("stu-offering-select");
  const tableEl = document.getElementById("stu-assignments-table");

  async function load() {
    tableEl.innerHTML = renderLoading();
    const data = await opsApi.listOfferingAssignments(select.value, {
      page: 1,
      page_size: 50,
    });
    tableEl.innerHTML = renderDataTable({
      columns: [
        { key: "title", label: "Title" },
        { key: "due_at", label: "Due At" },
        { key: "max_score", label: "Max Score" },
        {
          label: "Materials",
          render: (r) =>
            `<button class="btn btn-outline btn-sm stu-materials-btn" data-id="${r.id}" data-title="${escapeHtml(r.title)}" type="button">Materials</button>`,
        },
        {
          label: "Action",
          render: (r) =>
            `<button class="btn btn-primary btn-sm submit-asg-btn" data-id="${r.id}" data-title="${escapeHtml(r.title)}" type="button">Submit</button>`,
        },
      ],
      rows: data.items,
      emptyTitle: "No assignments for this course",
    });

    tableEl.querySelectorAll(".stu-materials-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        try {
          const files = await filesApi.listAssignmentAttachments(btn.dataset.id);
          openModal({
            title: `Materials: ${btn.dataset.title}`,
            bodyHtml: `<div id="stu-mat-list">${renderFileListHtml(files)}</div>`,
          });
          bindFileListActions(document.getElementById("stu-mat-list"));
        } catch (err) {
          showToast(err.message || "Failed to load assignment materials.", "error");
        } finally {
          btn.disabled = false;
        }
      });
    });

    tableEl.querySelectorAll(".submit-asg-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        openModal({
          title: `Submit: ${btn.dataset.title}`,
          bodyHtml: `
            <form id="stu-submit-form">
              <div class="form-group">
                <label class="form-label">Submission Text</label>
                <textarea name="content" rows="3" class="form-control" placeholder="Enter your answer or notes..."></textarea>
              </div>
              <div class="form-group">
                <label class="form-label">Upload File (optional, max 10 MB)</label>
                <input id="stu-sub-file" type="file" accept="${ALLOWED_EXTENSIONS.join(",")}" class="form-control" />
                <span id="stu-sub-file-info" class="text-muted"></span>
              </div>
              <div id="stu-upload-progress" class="text-muted hidden"></div>
              <button class="btn btn-primary btn-block" type="submit">Submit Assignment</button>
            </form>
          `,
        });
        const fileInput = document.getElementById("stu-sub-file");
        const fileInfo = document.getElementById("stu-sub-file-info");
        const progEl = document.getElementById("stu-upload-progress");
        fileInput?.addEventListener("change", () => {
          const f = fileInput.files[0];
          fileInfo.textContent = f ? `${f.name} (${formatBytes(f.size)})` : "";
        });

        const formEl = document.getElementById("stu-submit-form");
        formEl?.addEventListener("submit", async (e) => {
          e.preventDefault();
          const submitBtn = formEl.querySelector('button[type="submit"]');
          const file = fileInput.files[0];
          if (file) {
            const fileErr = validateClientFile(file, 10 * 1024 * 1024);
            if (fileErr) {
              showToast(fileErr, "error");
              return;
            }
          }
          submitBtn.disabled = true;
          try {
            const fd = Object.fromEntries(new FormData(formEl).entries());
            const submission = await opsApi.submitAssignment(btn.dataset.id, {
              content: fd.content || (file ? `Attached file: ${file.name}` : null),
            });
            if (file) {
              progEl.classList.remove("hidden");
              const uploadFd = new FormData();
              uploadFd.append("file", file);
              await filesApi.uploadSubmissionFile(submission.id, uploadFd, (pct) => {
                progEl.textContent = `Uploading file: ${pct}%`;
              });
            }
            closeModal();
            showToast("Assignment submitted!", "success");
          } catch (err) {
            showToast(err.message || "Submission failed.", "error");
          } finally {
            submitBtn.disabled = false;
          }
        });
      });
    });
  }

  select.addEventListener("change", load);
  await load();
}

async function renderStudentSubmissions(container) {
  const data = await opsApi.listMySubmissions({ page: 1, page_size: 50 });
  container.innerHTML = `
    <section class="card">
      <div class="card-header"><h2 class="card-title">My Submissions &amp; Grades</h2></div>
      ${renderDataTable({
        columns: [
          { key: "assignment_id", label: "Assignment ID" },
          { key: "submitted_at", label: "Submitted At" },
          {
            label: "Score",
            render: (r) =>
              r.score !== null ? escapeHtml(r.score) : renderStatusBadge("Pending", "warning"),
          },
          { key: "feedback", label: "Feedback" },
        ],
        rows: data.items,
        emptyTitle: "No submissions yet",
      })}
    </section>
  `;
}

async function renderStudentNotices(container) {
  const data = await opsApi.listNotices({ page: 1, page_size: 20 });
  container.innerHTML = `
    <section class="card">
      <div class="card-header"><h2 class="card-title">Notices</h2></div>
      ${renderDataTable({
        columns: [
          { key: "title", label: "Title" },
          { key: "body", label: "Message" },
          { key: "published_at", label: "Published" },
        ],
        rows: data.items,
        emptyTitle: "No notices available",
      })}
    </section>
  `;
}

async function renderStudentTimetable(container) {
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
        emptyTitle: "No timetable slots found",
      })}
    </section>
  `;
}

export async function renderStudentPage(container, routeId) {
  container.innerHTML = renderLoading("Loading student module...");
  try {
    switch (routeId) {
      case "dashboard":
        await renderStudentOverview(container);
        break;
      case "profile":
        await renderStudentProfile(container);
        break;
      case "courses":
        await renderStudentCourses(container);
        break;
      case "attendance":
        await renderStudentAttendance(container);
        break;
      case "assignments":
        await renderStudentAssignments(container);
        break;
      case "submissions":
        await renderStudentSubmissions(container);
        break;
      case "notices":
        await renderStudentNotices(container);
        break;
      case "timetable":
        await renderStudentTimetable(container);
        break;
      default:
        await renderStudentOverview(container);
    }
  } catch (err) {
    container.innerHTML = renderErrorState(err.message || "Failed to load data.");
  }
}
