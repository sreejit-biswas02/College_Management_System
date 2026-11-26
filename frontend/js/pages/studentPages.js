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

function formatStudentSemesterLabel(profile) {
  if (profile.is_completed || profile.current_semester_number > 8) {
    return "Completed (8 Semesters)";
  }
  const sem = profile.current_semester_number ?? profile.calculated_semester;
  return sem ? `Semester ${sem}` : profile.semester_status || "Not configured";
}

async function renderStudentOverview(container) {
  const [profile, enrollments, attendance, notices, timetable, submissions] =
    await Promise.all([
      opsApi.getMyStudentProfile(),
      opsApi.listMyEnrollments({ status: "enrolled", page: 1, page_size: 20 }),
      opsApi.getMyAttendance({ page: 1, page_size: 5 }),
      opsApi.listNotices({ page: 1, page_size: 5 }),
      opsApi.getMyTimetable(),
      opsApi.listMySubmissions({ page: 1, page_size: 50 }),
    ]);

  const submissionByAssignmentId = new Map(
    (submissions.items || []).map((s) => [s.assignment_id, s])
  );

  // Fetch assignments across enrolled offerings in parallel
  const assignmentLists = await Promise.all(
    (enrollments.items || []).slice(0, 10).map((e) =>
      opsApi
        .listOfferingAssignments(e.course_offering.id, { page: 1, page_size: 10 })
        .then((res) => res.items || [])
        .catch(() => [])
    )
  );
  const allAssignments = assignmentLists
    .flat()
    .sort((a, b) => new Date(a.due_at) - new Date(b.due_at))
    .slice(0, 6);

  const gradedCount = (submissions.items || []).filter(
    (s) => s.score !== null && s.score !== undefined
  ).length;

  container.innerHTML = `
    <section class="card" style="margin-bottom:1.25rem;">
      <div class="card-header" style="margin-bottom:0.75rem;">
        <div>
          <h2 class="card-title">${escapeHtml(profile.user.full_name)}</h2>
          <p class="text-muted" style="font-size:0.875rem;">
            ${escapeHtml(profile.roll_number)} &bull;
            ${escapeHtml(`${profile.department.code} — ${profile.department.name}`)} &bull;
            ${escapeHtml(formatStudentSemesterLabel(profile))} &bull;
            Batch ${escapeHtml(profile.admission_academic_year || `${profile.admission_year}-${profile.admission_year + 1}`)}
          </p>
        </div>
        ${renderStatusBadge(profile.user.is_active ? "Active" : "Inactive", profile.user.is_active ? "success" : "danger")}
      </div>
    </section>

    <section class="stats-grid">
      <div class="stat-card">
        <div class="text-muted">Enrolled Courses</div>
        <div class="stat-value">${escapeHtml(enrollments.total)}</div>
        <div class="stat-subtext">${escapeHtml(formatStudentSemesterLabel(profile))}</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Attendance</div>
        <div class="stat-value">${escapeHtml(attendance.attendance_percentage)}%</div>
        <div class="stat-subtext">${escapeHtml(`${attendance.present} present / ${attendance.total_sessions} sessions`)}</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Submissions</div>
        <div class="stat-value">${escapeHtml(submissions.total)}</div>
        <div class="stat-subtext">${escapeHtml(`${gradedCount} graded`)}</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Weekly Classes</div>
        <div class="stat-value">${escapeHtml(timetable.length)}</div>
        <div class="stat-subtext">Scheduled slots</div>
      </div>
    </section>

    <div class="dashboard-grid">
      <section class="card">
        <div class="card-header"><h2 class="card-title">Upcoming Assignments &amp; Status</h2></div>
        ${renderDataTable({
          columns: [
            { label: "Assignment", key: "title" },
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
              label: "Status",
              render: (r) => {
                const sub = submissionByAssignmentId.get(r.id);
                if (sub) {
                  return sub.score !== null && sub.score !== undefined
                    ? renderStatusBadge(`Graded: ${sub.score}/${r.max_score}`, "success")
                    : renderStatusBadge("Submitted", "info");
                }
                const overdue = new Date(r.due_at) < new Date();
                return renderStatusBadge(
                  overdue ? "Overdue" : "Pending",
                  overdue ? "danger" : "warning"
                );
              },
            },
          ],
          rows: allAssignments,
          emptyTitle: "No assignments scheduled",
          emptyDescription: "Assignments for your enrolled courses will appear here.",
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
              render: (r) =>
                escapeHtml(
                  r.course_offering?.course
                    ? `${r.course_offering.course.code} (${r.course_offering.section})`
                    : "Not assigned"
                ),
            },
            { label: "Room", render: (r) => escapeHtml(r.room || "TBA") },
          ],
          rows: timetable.slice(0, 6),
          emptyTitle: "No timetable slots",
          emptyDescription: "Your weekly class schedule will appear here once published.",
        })}
      </section>
    </div>

    <section class="card" style="margin-top:1.25rem;">
      <div class="card-header"><h2 class="card-title">Recent Notices</h2></div>
      ${renderDataTable({
        columns: [
          { key: "title", label: "Title" },
          { label: "Audience", render: (r) => escapeHtml(formatNoticeAudience(r)) },
          {
            label: "Published By",
            render: (r) => escapeHtml(r.posted_by_user?.full_name || "Administration"),
          },
          {
            label: "Published",
            render: (r) => escapeHtml(formatIndianDateTime(r.published_at)),
          },
        ],
        rows: notices.items,
        emptyTitle: "No notices available",
      })}
    </section>
  `;
}

async function renderStudentProfile(container) {
  const profile = await opsApi.getMyStudentProfile();
  const batch =
    profile.admission_academic_year ||
    `${profile.admission_year}-${profile.admission_year + 1}`;
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">My Student Profile</h2>
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
          <div class="profile-field-label">Student ID</div>
          <strong>${escapeHtml(profile.roll_number)}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Department</div>
          <strong>${escapeHtml(`${profile.department.code} — ${profile.department.name}`)}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Current Semester</div>
          <strong>${escapeHtml(formatStudentSemesterLabel(profile))}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Admission Academic Year</div>
          <strong>${escapeHtml(batch)}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Phone</div>
          <strong>${escapeHtml(profile.phone || "Not provided")}</strong>
        </div>
        <div class="profile-field">
          <div class="profile-field-label">Date of Birth</div>
          <strong>${escapeHtml(profile.date_of_birth ? formatIndianDate(profile.date_of_birth) : "Not provided")}</strong>
        </div>
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
          {
            label: "Course",
            render: (r) =>
              escapeHtml(
                `${r.course_offering.course.code} — ${r.course_offering.course.title}`
              ),
          },
          { label: "Section", render: (r) => escapeHtml(r.course_offering.section) },
          { label: "Credits", render: (r) => escapeHtml(r.course_offering.course.credits) },
          {
            label: "Faculty",
            render: (r) =>
              escapeHtml(
                `${r.course_offering.faculty.employee_id} — ${r.course_offering.faculty.user.full_name}`
              ),
          },
          {
            label: "Semester",
            render: (r) =>
              escapeHtml(
                `${r.course_offering.semester.name} (${r.course_offering.semester.academic_year})`
              ),
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
        emptyTitle: "Not enrolled in any courses",
      })}
    </section>
  `;
}

async function renderStudentAttendance(container) {
  const summary = await opsApi.getMyAttendance({ page: 1, page_size: 100 });
  container.innerHTML = `
    <section class="stats-grid">
      <div class="stat-card">
        <div class="text-muted">Attendance %</div>
        <div class="stat-value">${escapeHtml(summary.attendance_percentage)}%</div>
        <div class="stat-subtext">${escapeHtml(`${summary.late} late • ${summary.excused} excused`)}</div>
      </div>
      <div class="stat-card"><div class="text-muted">Total Sessions</div><div class="stat-value">${escapeHtml(summary.total_sessions)}</div></div>
      <div class="stat-card"><div class="text-muted">Present</div><div class="stat-value">${escapeHtml(summary.present)}</div></div>
      <div class="stat-card"><div class="text-muted">Absent</div><div class="stat-value">${escapeHtml(summary.absent)}</div></div>
    </section>
    <section class="card">
      <div class="card-header"><h2 class="card-title">Attendance History</h2></div>
      ${renderDataTable({
        columns: [
          {
            label: "Course",
            render: (r) =>
              escapeHtml(formatOfferingLabel(r.session?.course_offering, "Not available")),
          },
          {
            label: "Session Date",
            render: (r) =>
              r.session
                ? escapeHtml(
                    `${formatIndianDate(r.session.session_date)} (Session #${r.session.session_number})`
                  )
                : "Not available",
          },
          {
            label: "Topic",
            render: (r) => escapeHtml(r.session?.topic || "—"),
          },
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
          {
            label: "Marked At",
            render: (r) => escapeHtml(formatIndianDateTime(r.marked_at)),
          },
        ],
        rows: summary.records,
        emptyTitle: "No attendance records yet",
      })}
    </section>
  `;
}

async function renderStudentAssignments(container) {
  const [enrollments, mySubmissions] = await Promise.all([
    opsApi.listMyEnrollments({ status: "enrolled", page: 1, page_size: 50 }),
    opsApi.listMySubmissions({ page: 1, page_size: 100 }),
  ]);
  if (!enrollments.items.length) {
    container.innerHTML = `<section class="card">${renderEmptyState("No enrolled courses")}</section>`;
    return;
  }

  const submissionsByAsg = new Map(
    (mySubmissions.items || []).map((s) => [s.assignment_id, s])
  );

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">My Assignments</h2>
        <select id="stu-offering-select" class="form-control" style="max-width:340px;" aria-label="Filter by course offering">
          ${enrollments.items
            .map(
              (e) =>
                `<option value="${e.course_offering.id}">${escapeHtml(formatOfferingLabel(e.course_offering))}</option>`
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
    let data;
    try {
      data = await opsApi.listOfferingAssignments(select.value, {
        page: 1,
        page_size: 50,
      });
    } catch (err) {
      tableEl.innerHTML = renderErrorState(err.message || "Failed to load assignments.");
      return;
    }
    tableEl.innerHTML = renderDataTable({
      columns: [
        { key: "title", label: "Title" },
        { label: "Due At", render: (r) => escapeHtml(formatIndianDateTime(r.due_at)) },
        { key: "max_score", label: "Max Score" },
        {
          label: "Status",
          render: (r) => {
            const sub = submissionsByAsg.get(r.id);
            if (sub) {
              return sub.score !== null && sub.score !== undefined
                ? renderStatusBadge(`Graded (${sub.score}/${r.max_score})`, "success")
                : renderStatusBadge("Submitted", "info");
            }
            const overdue = new Date(r.due_at) < new Date();
            return renderStatusBadge(
              overdue ? "Overdue" : "Open",
              overdue ? "danger" : "warning"
            );
          },
        },
        {
          label: "Materials",
          render: (r) =>
            `<button class="btn btn-outline btn-sm stu-materials-btn" data-id="${r.id}" data-title="${escapeHtml(r.title)}" type="button">Materials</button>`,
        },
        {
          label: "Action",
          render: (r) => {
            const sub = submissionsByAsg.get(r.id);
            if (sub) {
              return '<span class="text-muted">Already submitted</span>';
            }
            return `<button class="btn btn-primary btn-sm submit-asg-btn" data-id="${r.id}" data-title="${escapeHtml(r.title)}" type="button">Submit</button>`;
          },
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
                <label class="form-label">Upload File(s) (optional, max 10 MB each)</label>
                <input id="stu-sub-file" type="file" multiple accept="${ALLOWED_EXTENSIONS.join(",")}" class="form-control" />
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
          const files = Array.from(fileInput.files || []);
          fileInfo.textContent = files
            .map((f) => `${f.name} (${formatBytes(f.size)})`)
            .join(", ");
        });

        const formEl = document.getElementById("stu-submit-form");
        formEl?.addEventListener("submit", async (e) => {
          e.preventDefault();
          const submitBtn = formEl.querySelector('button[type="submit"]');
          const files = Array.from(fileInput.files || []);
          const fd = Object.fromEntries(new FormData(formEl).entries());
          const trimmedContent = (fd.content || "").trim();
          if (!trimmedContent && files.length === 0) {
            showToast("Please enter submission text or attach a file.", "error");
            return;
          }
          for (const file of files) {
            const fileErr = validateClientFile(file, 10 * 1024 * 1024);
            if (fileErr) {
              showToast(fileErr, "error");
              return;
            }
          }
          submitBtn.disabled = true;
          try {
            const submission = await opsApi.submitAssignment(btn.dataset.id, {
              content:
                trimmedContent ||
                (files.length
                  ? `Attached file(s): ${files.map((f) => f.name).join(", ")}`
                  : null),
            });
            for (let i = 0; i < files.length; i += 1) {
              progEl.classList.remove("hidden");
              const uploadFd = new FormData();
              uploadFd.append("file", files[i]);
              await filesApi.uploadSubmissionFile(submission.id, uploadFd, (pct) => {
                progEl.textContent = `Uploading ${files[i].name} (${i + 1}/${files.length}): ${pct}%`;
              });
            }
            submissionsByAsg.set(Number(btn.dataset.id), submission);
            closeModal();
            showToast("Assignment submitted!", "success");
            await load();
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
          {
            label: "Assignment",
            render: (r) =>
              escapeHtml(r.assignment?.title || `Assignment #${r.assignment_id}`),
          },
          {
            label: "Course",
            render: (r) =>
              escapeHtml(formatOfferingLabel(r.assignment?.course_offering, "Not available")),
          },
          {
            label: "Submitted At",
            render: (r) => escapeHtml(formatIndianDateTime(r.submitted_at)),
          },
          {
            label: "Attachments",
            render: (r) =>
              renderFileListHtml(r.attachments || [], { compact: true }),
          },
          {
            label: "Score",
            render: (r) =>
              r.score !== null && r.score !== undefined
                ? renderStatusBadge(
                    `${r.score} / ${r.assignment?.max_score ?? "—"}`,
                    "success"
                  )
                : renderStatusBadge("Pending", "warning"),
          },
          { key: "feedback", label: "Feedback" },
        ],
        rows: data.items,
        emptyTitle: "No submissions yet",
      })}
    </section>
  `;
  bindFileListActions(container);
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
          { label: "Audience", render: (r) => escapeHtml(formatNoticeAudience(r)) },
          {
            label: "Published By",
            render: (r) => escapeHtml(r.posted_by_user?.full_name || "Administration"),
          },
          {
            label: "Published",
            render: (r) => escapeHtml(formatIndianDateTime(r.published_at)),
          },
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
          { label: "Day", render: (r) => escapeHtml(formatDayOfWeek(r.day_of_week)) },
          {
            label: "Time",
            render: (r) =>
              escapeHtml(`${formatTime12h(r.start_time)} – ${formatTime12h(r.end_time)}`),
          },
          {
            label: "Course",
            render: (r) =>
              escapeHtml(formatOfferingLabel(r.course_offering, "Not assigned")),
          },
          {
            label: "Faculty",
            render: (r) =>
              escapeHtml(
                r.course_offering?.faculty
                  ? `${r.course_offering.faculty.employee_id} — ${r.course_offering.faculty.user.full_name}`
                  : "Not assigned"
              ),
          },
          { label: "Room", render: (r) => escapeHtml(r.room || "TBA") },
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
