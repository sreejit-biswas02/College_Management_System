import * as adminApi from "../api/adminApi.js?v=5";
import * as opsApi from "../api/operationsApi.js";
import { renderDataTable } from "../components/dataTable.js";
import { closeModal, openModal } from "../components/modal.js";
import { renderPagination } from "../components/pagination.js";
import {
  initSearchableSelect,
  renderSearchableSelectField,
} from "../components/searchableSelect.js";
import { showToast } from "../components/toast.js";
import {
  escapeHtml,
  formatDayOfWeek,
  formatIndianDate,
  formatIndianDateTime,
  formatNoticeAudience,
  formatOfferingLabel,
  formatTime12h,
  renderErrorState,
  renderLoading,
  renderSearchInput,
  renderStatusBadge,
} from "../components/ui.js";

const state = {
  page: 1,
  search: "",
  showArchived: false,
};

function bindPagination(data, reload) {
  document.getElementById("pg-prev")?.addEventListener("click", () => {
    if (state.page > 1) {
      state.page -= 1;
      reload();
    }
  });
  document.getElementById("pg-next")?.addEventListener("click", () => {
    if (state.page < (data.pages || 1)) {
      state.page += 1;
      reload();
    }
  });
}

function openFormModal({ title, fieldsHtml, onMount, onSubmit }) {
  let selectors = [];
  openModal({
    title,
    bodyHtml: `<form id="modal-entity-form">${fieldsHtml}<button class="btn btn-primary btn-block" type="submit">Save</button></form>`,
    onClose: () => {
      selectors.forEach((sel) => sel?.ctrl?.destroy?.());
      selectors = [];
    },
  });
  const formEl = document.getElementById("modal-entity-form");
  selectors = onMount ? onMount(formEl) || [] : [];

  formEl?.addEventListener("submit", async (e) => {
    e.preventDefault();
    let hasMissing = false;
    for (const sel of selectors) {
      if (sel?.required && !sel.ctrl?.getValue()) {
        sel.ctrl?.setError(sel.errorMessage || "Please select an option.");
        hasMissing = true;
      }
    }
    if (hasMissing) {
      return;
    }

    const submitBtn = formEl.querySelector('button[type="submit"]');
    const originalText = submitBtn ? submitBtn.textContent : "Save";
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Saving...";
    }
    try {
      const formData = new FormData(formEl);
      await onSubmit(Object.fromEntries(formData.entries()));
      closeModal();
    } catch (err) {
      showToast(err.message || "Operation failed.", "error");
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
      }
    }
  });
}

function mountDepartmentSelect(id = "dept-select") {
  return {
    required: true,
    errorMessage: "Please select a department.",
    ctrl: initSearchableSelect({
      id,
      emptyMessage: "No active departments found.",
      loadErrorMessage: "Failed to load departments.",
      fetchOptions: ({ search, page, pageSize }) =>
        adminApi.listDepartments({
          search,
          is_active: true,
          page,
          page_size: pageSize,
        }),
      mapOption: (d) => ({
        value: String(d.id),
        label: `${d.code} — ${d.name}`,
        description: d.description || "Active department",
      }),
    }),
  };
}

function mountCourseSelect(id = "course-select") {
  return {
    required: true,
    errorMessage: "Please select a course.",
    ctrl: initSearchableSelect({
      id,
      emptyMessage: "No courses found.",
      loadErrorMessage: "Failed to load courses.",
      fetchOptions: ({ search, page, pageSize }) =>
        adminApi.listCourses({ search, page, page_size: pageSize }),
      mapOption: (c) => ({
        value: String(c.id),
        label: `${c.code} — ${c.title}`,
        description: `${c.department.code} • ${c.credits} credits`,
      }),
    }),
  };
}

function mountSemesterSelect(id = "semester-select") {
  return {
    required: true,
    errorMessage: "Please select a semester.",
    ctrl: initSearchableSelect({
      id,
      emptyMessage: "No semesters found.",
      loadErrorMessage: "Failed to load semesters.",
      fetchOptions: ({ search, page, pageSize }) =>
        adminApi.listSemesters({ search, page, page_size: pageSize }),
      mapOption: (s) => {
        const semType = s.semester_type || (s.term_number % 2 === 1 ? "Odd" : "Even");
        const dateRange =
          s.start_date && s.end_date
            ? ` • ${formatIndianDate(s.start_date)} – ${formatIndianDate(s.end_date)}`
            : "";
        return {
          value: String(s.id),
          label: `${s.name} (${semType}) — ${s.academic_year}`,
          description: `Semester ${s.term_number}${dateRange} • ${s.is_active ? "Active" : "Inactive"}`,
        };
      },
    }),
  };
}

function mountFacultySelect(id = "faculty-select") {
  return {
    required: true,
    errorMessage: "Please select an active faculty member.",
    ctrl: initSearchableSelect({
      id,
      emptyMessage: "No active faculty members found.",
      loadErrorMessage: "Failed to load faculty members.",
      fetchOptions: ({ search, page, pageSize }) =>
        adminApi.listFaculty({
          search,
          is_active: true,
          page,
          page_size: pageSize,
        }),
      mapOption: (f) => ({
        value: String(f.id),
        label: `${f.employee_id} — ${f.user.full_name}`,
        description: `${f.designation} • ${f.department.code} • ${f.user.email}`,
      }),
    }),
  };
}

function mountStudentSelect(id = "student-select") {
  return {
    required: true,
    errorMessage: "Please select an active student.",
    ctrl: initSearchableSelect({
      id,
      emptyMessage: "No active students found.",
      loadErrorMessage: "Failed to load students.",
      fetchOptions: ({ search, page, pageSize }) =>
        adminApi.listStudents({
          search,
          is_archived: false,
          is_active: true,
          page,
          page_size: pageSize,
        }),
      mapOption: (s) => ({
        value: String(s.id),
        label: `${s.roll_number} — ${s.user.full_name}`,
        description: `${s.department.code} • Sem ${s.current_semester_number} • ${s.user.email}`,
      }),
    }),
  };
}

function mountOfferingSelect(id = "offering-select") {
  return {
    required: true,
    errorMessage: "Please select a course offering.",
    ctrl: initSearchableSelect({
      id,
      emptyMessage: "No active course offerings found.",
      loadErrorMessage: "Failed to load course offerings.",
      fetchOptions: ({ search, page, pageSize }) =>
        adminApi.listOfferings({
          search,
          is_active: true,
          page,
          page_size: pageSize,
        }),
      mapOption: (o) => ({
        value: String(o.id),
        label: `${o.course.code} — ${o.course.title} (Sec ${o.section})`,
        description: `${o.semester.name} (${o.semester.academic_year}) • ${o.faculty.employee_id} — ${o.faculty.user.full_name}`,
      }),
    }),
  };
}

async function renderAdminOverview(container) {
  const [summary, notices, offerings] = await Promise.all([
    adminApi.getAdminDashboardSummary(),
    opsApi.listNotices({ page: 1, page_size: 5 }),
    adminApi.listOfferings({ page: 1, page_size: 5, is_active: true }),
  ]);

  const cards = [
    ["Total Students", summary.total_students, `${summary.active_students} active`],
    ["Total Faculty", summary.total_faculty, "Registered teaching staff"],
    ["Active Departments", summary.total_departments, "Academic departments"],
    ["Active Courses", summary.active_courses, "Catalog courses"],
    ["Active Offerings", summary.active_offerings, "Currently running sections"],
    ["Total Enrollments", summary.total_enrollments, "Active student enrollments"],
    [
      "Attendance Rate",
      `${summary.attendance_rate_percentage}%`,
      `${summary.total_attendance_sessions} sessions recorded`,
    ],
    [
      "Pending Submissions",
      summary.pending_submissions,
      `Across ${summary.total_assignments} assignment(s)`,
    ],
  ];

  container.innerHTML = `
    <section class="stats-grid">
      ${cards
        .map(
          ([label, val, sub]) => `
        <div class="stat-card">
          <div class="text-muted">${escapeHtml(label)}</div>
          <div class="stat-value">${escapeHtml(val)}</div>
          <div class="stat-subtext">${escapeHtml(sub)}</div>
        </div>`
        )
        .join("")}
    </section>

    <div class="dashboard-grid">
      <section class="card">
        <div class="card-header"><h2 class="card-title">Active Course Offerings</h2></div>
        ${renderDataTable({
          columns: [
            { label: "Course", render: (r) => escapeHtml(`${r.course.code} — ${r.course.title}`) },
            { label: "Semester", render: (r) => escapeHtml(`${r.semester.name} (${r.semester.academic_year})`) },
            {
              label: "Faculty",
              render: (r) =>
                escapeHtml(`${r.faculty.employee_id} — ${r.faculty.user.full_name}`),
            },
            { key: "section", label: "Sec" },
          ],
          rows: offerings.items,
          emptyTitle: "No active course offerings",
        })}
      </section>

      <section class="card">
        <div class="card-header"><h2 class="card-title">Recent Notices</h2></div>
        ${renderDataTable({
          columns: [
            { key: "title", label: "Title" },
            { label: "Audience", render: (r) => escapeHtml(formatNoticeAudience(r)) },
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
          ],
          rows: notices.items,
          emptyTitle: "No notices published",
        })}
      </section>
    </div>
  `;
}

function formatStudentSemesterBadge(r) {
  const sem = r.current_semester_number ?? r.calculated_semester;
  if (r.is_completed || sem > 8) {
    return renderStatusBadge("Completed (Sem 8)", "info");
  }
  return `Semester ${escapeHtml(sem)}`;
}

function buildAdmissionAcademicYearOptions(selectedYear = 2026) {
  const years = [];
  for (let yr = 2020; yr <= 2030; yr += 1) {
    years.push(
      `<option value="${yr}" ${Number(selectedYear) === yr ? "selected" : ""}>${yr}-${yr + 1}</option>`
    );
  }
  return years.join("");
}

async function updateSemesterPreviewBox(yearValue, previewEl) {
  if (!previewEl || !yearValue) return;
  previewEl.textContent = "Calculating semester...";
  try {
    const res = await adminApi.previewStudentSemester(Number(yearValue));
    if (res.is_completed) {
      previewEl.textContent = `Completed (8 Semesters) • Academic Year: ${res.active_academic_year}`;
    } else if (res.calculated_semester) {
      previewEl.textContent = `Calculated Semester: ${res.calculated_semester} (Academic Year: ${res.active_academic_year})`;
    } else {
      previewEl.textContent = res.semester_status || "Invalid Admission Year";
    }
  } catch (err) {
    previewEl.textContent = err.message || "Unable to calculate semester.";
  }
}

async function renderStudents(container) {
  const data = await adminApi.listStudents({
    page: state.page,
    page_size: 10,
    search: state.search,
    is_archived: state.showArchived,
  });

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <div style="display:flex;gap:0.6rem;align-items:center;flex-wrap:wrap;">
          ${renderSearchInput({
            id: "entity-search",
            placeholder: "Search name, email, student ID...",
            value: state.search,
          })}
          <select id="student-archive-filter" class="form-control" style="max-width:200px;" aria-label="Student archive filter">
            <option value="false" ${!state.showArchived ? "selected" : ""}>Active &amp; Inactive</option>
            <option value="true" ${state.showArchived ? "selected" : ""}>Archived Students</option>
          </select>
        </div>
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap;">
          <button id="promote-students-btn" class="btn btn-outline btn-sm" type="button">Promote Students to Next Semester</button>
          <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Add Student</button>
        </div>
      </div>
      ${renderDataTable({
        columns: [
          { key: "roll_number", label: "Student ID" },
          { label: "Name", render: (r) => escapeHtml(r.user.full_name) },
          { label: "Email", render: (r) => escapeHtml(r.user.email) },
          {
            label: "Department",
            render: (r) => escapeHtml(`${r.department.code} — ${r.department.name}`),
          },
          {
            label: "Admission Year",
            render: (r) =>
              escapeHtml(
                r.admission_academic_year ||
                  `${r.admission_year}-${r.admission_year + 1}`
              ),
          },
          { label: "Semester", render: (r) => formatStudentSemesterBadge(r) },
          {
            label: "Status",
            render: (r) =>
              r.is_archived
                ? renderStatusBadge("Archived", "warning")
                : renderStatusBadge(
                    r.user.is_active ? "Active" : "Inactive",
                    r.user.is_active ? "success" : "danger"
                  ),
          },
          {
            label: "Action",
            render: (r) =>
              r.is_archived
                ? `<button class="btn btn-outline btn-sm restore-student-btn" data-id="${r.id}" data-name="${escapeHtml(r.user.full_name)}" data-email="${escapeHtml(r.user.email)}" data-roll="${escapeHtml(r.roll_number)}" type="button">Restore</button>`
                : `<div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
                    <button class="btn btn-outline btn-sm edit-student-btn" data-id="${r.id}" type="button">Edit</button>
                    <button class="btn btn-outline btn-sm toggle-active-btn" data-id="${r.id}" data-next="${!r.user.is_active}" type="button">${
                      r.user.is_active ? "Deactivate" : "Activate"
                    }</button>
                    <button class="btn btn-danger btn-sm delete-student-btn" data-id="${r.id}" data-name="${escapeHtml(r.user.full_name)}" data-email="${escapeHtml(r.user.email)}" data-roll="${escapeHtml(r.roll_number)}" type="button">Archive</button>
                  </div>`,
          },
        ],
        rows: data.items,
        emptyTitle: state.showArchived ? "No archived students" : "No students found",
      })}
      ${renderPagination(data)}
    </section>
  `;

  document.getElementById("entity-search")?.addEventListener("change", (e) => {
    state.search = e.target.value;
    state.page = 1;
    renderStudents(container);
  });

  document
    .getElementById("student-archive-filter")
    ?.addEventListener("change", (e) => {
      state.showArchived = e.target.value === "true";
      state.page = 1;
      renderStudents(container);
    });

  bindPagination(data, () => renderStudents(container));

  container.querySelectorAll(".toggle-active-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await adminApi.setStudentActive(
          btn.dataset.id,
          btn.dataset.next === "true"
        );
        showToast("Student status updated.", "success");
        renderStudents(container);
      } catch (err) {
        showToast(err.message || "Failed to update student status.", "error");
        btn.disabled = false;
      }
    });
  });

  container.querySelectorAll(".delete-student-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const { id, name, email, roll } = btn.dataset;
      openModal({
        title: "Archive Student Account",
        bodyHtml: `
          <div style="display:flex;flex-direction:column;gap:0.75rem;">
            <p>Are you sure you want to archive this student?</p>
            <div style="padding:0.75rem;border:1px solid var(--color-border);border-radius:6px;background:var(--color-surface-muted);">
              <div><strong>Name:</strong> ${escapeHtml(name)}</div>
              <div><strong>Email:</strong> ${escapeHtml(email)}</div>
              <div><strong>Student ID:</strong> ${escapeHtml(roll)}</div>
            </div>
            <p class="text-muted">
              The student's account will be archived and they will <strong>no longer be able to log in</strong>.
            </p>
            <p class="text-muted">
              All academic records (enrollments, attendance, assignment submissions, and grades) will be <strong>retained</strong>.
            </p>
          </div>
        `,
        footerHtml: `
          <button id="archive-cancel-btn" class="btn btn-outline" type="button">Cancel</button>
          <button id="archive-confirm-btn" class="btn btn-danger" type="button">Archive Student</button>
        `,
      });

      document
        .getElementById("archive-cancel-btn")
        ?.addEventListener("click", closeModal);
      const confirmBtn = document.getElementById("archive-confirm-btn");
      confirmBtn?.addEventListener("click", async () => {
        confirmBtn.disabled = true;
        try {
          await adminApi.archiveStudent(id);
          closeModal();
          showToast("Student archived. Academic records retained.", "success");
          await renderStudents(container);
        } catch (err) {
          showToast(err.message || "Failed to archive student.", "error");
          confirmBtn.disabled = false;
        }
      });
    });
  });

  container.querySelectorAll(".restore-student-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const { id, name, email, roll } = btn.dataset;
      openModal({
        title: "Restore Archived Student",
        bodyHtml: `
          <p>Restore <strong>${escapeHtml(name)}</strong> (${escapeHtml(roll)}, ${escapeHtml(email)}) to the main student list?</p>
          <p class="text-muted" style="margin-top:0.5rem;">Login access remains disabled until you explicitly activate the account.</p>
        `,
        footerHtml: `
          <button id="restore-cancel-btn" class="btn btn-outline" type="button">Cancel</button>
          <button id="restore-confirm-btn" class="btn btn-primary" type="button">Restore Student</button>
        `,
      });
      document
        .getElementById("restore-cancel-btn")
        ?.addEventListener("click", closeModal);
      const confirmBtn = document.getElementById("restore-confirm-btn");
      confirmBtn?.addEventListener("click", async () => {
        confirmBtn.disabled = true;
        try {
          await adminApi.restoreStudent(id);
          closeModal();
          showToast("Student restored (account remains inactive).", "success");
          await renderStudents(container);
        } catch (err) {
          showToast(err.message || "Failed to restore student.", "error");
          confirmBtn.disabled = false;
        }
      });
    });
  });

  container.querySelectorAll(".edit-student-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const stu = data.items.find((item) => String(item.id) === btn.dataset.id);
      if (!stu) return;
      let deptChanged = false;
      let yearChanged = false;

      openFormModal({
        title: `Edit Student (${stu.roll_number})`,
        fieldsHtml: `
          <div class="form-group">
            <label class="form-label" for="edit-stu-roll">Student ID <span class="required-star">*</span></label>
            <input id="edit-stu-roll" name="roll_number" value="${escapeHtml(stu.roll_number)}" class="form-control" required />
            <small class="text-muted">Format: S-DEPTCODE-YYYY-XXX</small>
          </div>
          <div class="form-group"><label class="form-label">Full Name <span class="required-star">*</span></label><input name="full_name" value="${escapeHtml(stu.user.full_name)}" class="form-control" required /></div>
          <div class="form-group"><label class="form-label">Email <span class="required-star">*</span></label><input name="email" type="email" value="${escapeHtml(stu.user.email)}" class="form-control" required /></div>
          ${renderSearchableSelectField({
            id: "edit-student-dept-select",
            name: "department_id",
            label: "Department",
            placeholder: "Search department by code or name...",
            required: true,
          })}
          <div class="form-group">
            <label class="form-label" for="edit-stu-adm-year">Admission Academic Year <span class="required-star">*</span></label>
            <select id="edit-stu-adm-year" name="admission_year" class="form-control" required>
              ${buildAdmissionAcademicYearOptions(stu.admission_year)}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Calculated Semester (Auto)</label>
            <div id="edit-stu-sem-preview" class="form-control" aria-readonly="true">Calculating...</div>
          </div>
          <div id="edit-stu-recalc-wrap" class="form-group hidden">
            <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;">
              <input id="edit-stu-recalc" name="recalculate_id" type="checkbox" value="true" />
              <span>Recalculate Student ID for the updated department / admission year</span>
            </label>
          </div>
          <div class="form-group"><label class="form-label">Phone</label><input name="phone" value="${escapeHtml(stu.phone || "")}" class="form-control" /></div>
          <div class="form-group"><label class="form-label">Date of Birth</label><input name="date_of_birth" type="date" value="${escapeHtml(stu.date_of_birth || "")}" class="form-control" /></div>
          <div class="form-group">
            <label class="form-label">Account Status</label>
            <select name="is_active" class="form-control">
              <option value="true" ${stu.user.is_active ? "selected" : ""}>Active</option>
              <option value="false" ${!stu.user.is_active ? "selected" : ""}>Inactive</option>
            </select>
          </div>
        `,
        onMount: () => {
          const deptSel = initSearchableSelect({
            id: "edit-student-dept-select",
            emptyMessage: "No active departments found.",
            loadErrorMessage: "Failed to load departments.",
            fetchOptions: ({ search, page, pageSize }) =>
              adminApi.listDepartments({
                search,
                is_active: true,
                page,
                page_size: pageSize,
              }),
            mapOption: (d) => ({
              value: String(d.id),
              label: `${d.code} — ${d.name}`,
              description: d.description || "Active department",
            }),
            onChange: (val) => {
              deptChanged = Boolean(val && Number(val) !== stu.department_id);
              const wrap = document.getElementById("edit-stu-recalc-wrap");
              if (wrap) {
                wrap.classList.toggle("hidden", !(deptChanged || yearChanged));
              }
            },
          });
          deptSel?.setValue({
            value: String(stu.department.id),
            label: `${stu.department.code} — ${stu.department.name}`,
          });

          const yearEl = document.getElementById("edit-stu-adm-year");
          const previewEl = document.getElementById("edit-stu-sem-preview");
          updateSemesterPreviewBox(yearEl?.value, previewEl);
          yearEl?.addEventListener("change", () => {
            yearChanged = Number(yearEl.value) !== stu.admission_year;
            const wrap = document.getElementById("edit-stu-recalc-wrap");
            if (wrap) {
              wrap.classList.toggle("hidden", !(deptChanged || yearChanged));
            }
            updateSemesterPreviewBox(yearEl.value, previewEl);
          });

          return [
            {
              required: true,
              errorMessage: "Please select a department.",
              ctrl: deptSel,
            },
          ];
        },
        onSubmit: async (form) => {
          const recalc = form.recalculate_id === "true";
          const payload = {
            full_name: form.full_name,
            email: form.email,
            department_id: Number(form.department_id),
            admission_year: Number(form.admission_year),
            phone: form.phone || null,
            date_of_birth: form.date_of_birth || null,
            is_active: form.is_active === "true",
            recalculate_id: recalc,
          };
          if (!recalc && form.roll_number) {
            payload.roll_number = form.roll_number;
          }
          const updated = await adminApi.updateStudent(stu.id, payload);
          showToast(`Student updated (${updated.roll_number}).`, "success");
          renderStudents(container);
        },
      });
    });
  });

  document
    .getElementById("promote-students-btn")
    ?.addEventListener("click", async () => {
      const btn = document.getElementById("promote-students-btn");
      if (btn) btn.disabled = true;
      try {
        const preview = await adminApi.getPromotionPreview();
        const breakdownHtml = preview.breakdown.length
          ? `<ul style="margin:0.5rem 0 0 1.25rem;">
              ${preview.breakdown
                .map(
                  (b) =>
                    `<li>Semester ${escapeHtml(b.old_semester)} &rarr; Semester ${escapeHtml(b.new_semester)}: <strong>${escapeHtml(b.count)}</strong> active student(s)</li>`
                )
                .join("")}
            </ul>`
          : `<p class="text-muted">No active odd-semester students are eligible for promotion.</p>`;

        openModal({
          title: `Promote Students (${preview.academic_year})`,
          bodyHtml: `
            <div style="display:flex;flex-direction:column;gap:0.75rem;">
              <p>This operation transitions eligible active students from odd semesters to the next even semester.</p>
              <div style="padding:0.75rem;border:1px solid var(--color-border);border-radius:6px;background:var(--color-surface-muted);">
                <div><strong>Eligible Active Students:</strong> ${escapeHtml(preview.eligible_count)}</div>
                <div><strong>Inactive Students Skipped:</strong> ${escapeHtml(preview.inactive_skipped_count)}</div>
                <div><strong>Already Promoted (${escapeHtml(preview.academic_year)}):</strong> ${escapeHtml(preview.already_promoted_count)}</div>
                ${breakdownHtml}
              </div>
              ${
                !preview.can_promote && preview.already_promoted_count > 0
                  ? `<p class="text-danger">Promotion for ${escapeHtml(preview.academic_year)} has already been performed.</p>`
                  : ""
              }
            </div>
          `,
          footerHtml: `
            <button id="promo-cancel-btn" class="btn btn-outline" type="button">Cancel</button>
            <button id="promo-confirm-btn" class="btn btn-primary" type="button" ${
              preview.can_promote ? "" : "disabled"
            }>Confirm Promotion</button>
          `,
        });

        document
          .getElementById("promo-cancel-btn")
          ?.addEventListener("click", closeModal);
        const confirmBtn = document.getElementById("promo-confirm-btn");
        confirmBtn?.addEventListener("click", async () => {
          confirmBtn.disabled = true;
          confirmBtn.textContent = "Promoting...";
          try {
            const res = await adminApi.promoteStudentsSemester();
            closeModal();
            showToast(res.message, "success");
            await renderStudents(container);
          } catch (err) {
            showToast(err.message || "Promotion failed.", "error");
            confirmBtn.disabled = false;
            confirmBtn.textContent = "Confirm Promotion";
          }
        });
      } catch (err) {
        showToast(err.message || "Failed to load promotion preview.", "error");
      } finally {
        if (btn) btn.disabled = false;
      }
    });

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Student",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Full Name <span class="required-star">*</span></label><input name="full_name" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Email <span class="required-star">*</span></label><input name="email" type="email" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Password <span class="required-star">*</span></label><input name="password" type="password" class="form-control" placeholder="Min 8 chars, Aa1!" required /></div>
        ${renderSearchableSelectField({
          id: "student-dept-select",
          name: "department_id",
          label: "Department",
          placeholder: "Search department by code or name...",
          required: true,
        })}
        <div class="form-group">
          <label class="form-label" for="create-stu-adm-year">Admission Academic Year <span class="required-star">*</span></label>
          <select id="create-stu-adm-year" name="admission_year" class="form-control" required>
            ${buildAdmissionAcademicYearOptions(2026)}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Calculated Semester (Auto)</label>
          <div id="create-stu-sem-preview" class="form-control" aria-readonly="true">Calculating...</div>
        </div>
      `,
      onMount: () => {
        const yearEl = document.getElementById("create-stu-adm-year");
        const previewEl = document.getElementById("create-stu-sem-preview");
        updateSemesterPreviewBox(yearEl?.value, previewEl);
        yearEl?.addEventListener("change", () =>
          updateSemesterPreviewBox(yearEl.value, previewEl)
        );
        return [mountDepartmentSelect("student-dept-select")];
      },
      onSubmit: async (form) => {
        const created = await adminApi.createStudent({
          ...form,
          department_id: Number(form.department_id),
          admission_year: Number(form.admission_year),
        });
        showToast(
          `Student created successfully. Generated Student ID: ${created.roll_number}`,
          "success"
        );
        renderStudents(container);
      },
    });
  });
}

async function renderFaculty(container) {
  const data = await adminApi.listFaculty({
    page: state.page,
    page_size: 10,
    search: state.search,
  });

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        ${renderSearchInput({
          id: "entity-search",
          placeholder: "Search name, email, faculty ID...",
          value: state.search,
        })}
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Add Faculty</button>
      </div>
      ${renderDataTable({
        columns: [
          { key: "employee_id", label: "Faculty ID" },
          { label: "Name", render: (r) => escapeHtml(r.user.full_name) },
          { label: "Email", render: (r) => escapeHtml(r.user.email) },
          { key: "designation", label: "Designation" },
          {
            label: "Department",
            render: (r) => escapeHtml(`${r.department.code} — ${r.department.name}`),
          },
          {
            label: "Status",
            render: (r) =>
              renderStatusBadge(
                r.user.is_active ? "Active" : "Inactive",
                r.user.is_active ? "success" : "danger"
              ),
          },
          {
            label: "Action",
            render: (r) =>
              `<div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
                <button class="btn btn-outline btn-sm edit-faculty-btn" data-id="${r.id}" type="button">Edit</button>
                <button class="btn btn-outline btn-sm toggle-active-btn" data-id="${r.id}" data-next="${!r.user.is_active}" type="button">${
                  r.user.is_active ? "Deactivate" : "Activate"
                }</button>
              </div>`,
          },
        ],
        rows: data.items,
      })}
      ${renderPagination(data)}
    </section>
  `;

  document.getElementById("entity-search")?.addEventListener("change", (e) => {
    state.search = e.target.value;
    state.page = 1;
    renderFaculty(container);
  });
  bindPagination(data, () => renderFaculty(container));
  container.querySelectorAll(".toggle-active-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await adminApi.setFacultyActive(
          btn.dataset.id,
          btn.dataset.next === "true"
        );
        showToast("Faculty status updated.", "success");
        renderFaculty(container);
      } catch (err) {
        showToast(err.message || "Failed to update faculty status.", "error");
        btn.disabled = false;
      }
    });
  });

  container.querySelectorAll(".edit-faculty-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const fac = data.items.find((item) => String(item.id) === btn.dataset.id);
      if (!fac) return;

      openFormModal({
        title: `Edit Faculty (${fac.employee_id})`,
        fieldsHtml: `
          <div class="form-group">
            <label class="form-label" for="edit-fac-emp">Faculty ID <span class="required-star">*</span></label>
            <input id="edit-fac-emp" name="employee_id" value="${escapeHtml(fac.employee_id)}" class="form-control" required />
            <small class="text-muted">Format: F-DEPTCODE-XXX</small>
          </div>
          <div class="form-group"><label class="form-label">Full Name <span class="required-star">*</span></label><input name="full_name" value="${escapeHtml(fac.user.full_name)}" class="form-control" required /></div>
          <div class="form-group"><label class="form-label">Email <span class="required-star">*</span></label><input name="email" type="email" value="${escapeHtml(fac.user.email)}" class="form-control" required /></div>
          ${renderSearchableSelectField({
            id: "edit-faculty-dept-select",
            name: "department_id",
            label: "Department",
            placeholder: "Search department by code or name...",
            required: true,
          })}
          <div id="edit-fac-recalc-wrap" class="form-group hidden">
            <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;">
              <input name="recalculate_id" type="checkbox" value="true" />
              <span>Recalculate Faculty ID for the new department</span>
            </label>
          </div>
          <div class="form-group"><label class="form-label">Designation <span class="required-star">*</span></label><input name="designation" value="${escapeHtml(fac.designation)}" class="form-control" required /></div>
          <div class="form-group"><label class="form-label">Phone</label><input name="phone" value="${escapeHtml(fac.phone || "")}" class="form-control" /></div>
          <div class="form-group"><label class="form-label">Joining Date</label><input name="joining_date" type="date" value="${escapeHtml(fac.joining_date || "")}" class="form-control" /></div>
          <div class="form-group">
            <label class="form-label">Account Status</label>
            <select name="is_active" class="form-control">
              <option value="true" ${fac.user.is_active ? "selected" : ""}>Active</option>
              <option value="false" ${!fac.user.is_active ? "selected" : ""}>Inactive</option>
            </select>
          </div>
        `,
        onMount: () => {
          const deptSel = initSearchableSelect({
            id: "edit-faculty-dept-select",
            emptyMessage: "No active departments found.",
            loadErrorMessage: "Failed to load departments.",
            fetchOptions: ({ search, page, pageSize }) =>
              adminApi.listDepartments({
                search,
                is_active: true,
                page,
                page_size: pageSize,
              }),
            mapOption: (d) => ({
              value: String(d.id),
              label: `${d.code} — ${d.name}`,
              description: d.description || "Active department",
            }),
            onChange: (val) => {
              const wrap = document.getElementById("edit-fac-recalc-wrap");
              if (wrap) {
                wrap.classList.toggle(
                  "hidden",
                  !(val && Number(val) !== fac.department_id)
                );
              }
            },
          });
          deptSel?.setValue({
            value: String(fac.department.id),
            label: `${fac.department.code} — ${fac.department.name}`,
          });
          return [
            {
              required: true,
              errorMessage: "Please select a department.",
              ctrl: deptSel,
            },
          ];
        },
        onSubmit: async (form) => {
          const recalc = form.recalculate_id === "true";
          const payload = {
            full_name: form.full_name,
            email: form.email,
            department_id: Number(form.department_id),
            designation: form.designation,
            phone: form.phone || null,
            joining_date: form.joining_date || null,
            is_active: form.is_active === "true",
            recalculate_id: recalc,
          };
          if (!recalc && form.employee_id) {
            payload.employee_id = form.employee_id;
          }
          const updated = await adminApi.updateFaculty(fac.id, payload);
          showToast(`Faculty updated (${updated.employee_id}).`, "success");
          renderFaculty(container);
        },
      });
    });
  });

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Faculty",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Full Name <span class="required-star">*</span></label><input name="full_name" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Email <span class="required-star">*</span></label><input name="email" type="email" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Password <span class="required-star">*</span></label><input name="password" type="password" class="form-control" placeholder="Min 8 chars, Aa1!" required /></div>
        ${renderSearchableSelectField({
          id: "faculty-dept-select",
          name: "department_id",
          label: "Department",
          placeholder: "Search department by code or name...",
          required: true,
        })}
        <div class="form-group"><label class="form-label">Designation <span class="required-star">*</span></label><input name="designation" class="form-control" placeholder="Assistant Professor" required /></div>
      `,
      onMount: () => [mountDepartmentSelect("faculty-dept-select")],
      onSubmit: async (form) => {
        const created = await adminApi.createFaculty({
          ...form,
          department_id: Number(form.department_id),
        });
        showToast(
          `Faculty created successfully. Generated Faculty ID: ${created.employee_id}`,
          "success"
        );
        renderFaculty(container);
      },
    });
  });
}

async function renderDepartments(container) {
  const data = await adminApi.listDepartments({
    page: state.page,
    page_size: 10,
    search: state.search,
  });
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        ${renderSearchInput({
          id: "entity-search",
          placeholder: "Search department code or name...",
          value: state.search,
        })}
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Add Department</button>
      </div>
      ${renderDataTable({
        columns: [
          { key: "code", label: "Code" },
          { key: "name", label: "Department Name" },
          { key: "description", label: "Description" },
          {
            label: "Status",
            render: (r) =>
              renderStatusBadge(
                r.is_active ? "Active" : "Inactive",
                r.is_active ? "success" : "danger"
              ),
          },
          {
            label: "Action",
            render: (r) =>
              `<div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
                <button class="btn btn-outline btn-sm edit-dept-btn" data-id="${r.id}" type="button">Edit</button>
                <button class="btn btn-outline btn-sm toggle-active-btn" data-id="${r.id}" data-next="${!r.is_active}" type="button">${
                  r.is_active ? "Deactivate" : "Activate"
                }</button>
              </div>`,
          },
        ],
        rows: data.items,
      })}
      ${renderPagination(data)}
    </section>
  `;
  document.getElementById("entity-search")?.addEventListener("change", (e) => {
    state.search = e.target.value;
    state.page = 1;
    renderDepartments(container);
  });
  bindPagination(data, () => renderDepartments(container));
  container.querySelectorAll(".toggle-active-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await adminApi.setDepartmentActive(btn.dataset.id, btn.dataset.next === "true");
        showToast("Department updated.", "success");
        renderDepartments(container);
      } catch (err) {
        showToast(err.message || "Failed to update department.", "error");
        btn.disabled = false;
      }
    });
  });

  container.querySelectorAll(".edit-dept-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dept = data.items.find((d) => String(d.id) === btn.dataset.id);
      if (!dept) return;
      openFormModal({
        title: `Edit Department (${dept.code})`,
        fieldsHtml: `
          <div class="form-group"><label class="form-label">Code <span class="required-star">*</span></label><input name="code" value="${escapeHtml(dept.code)}" class="form-control" required /></div>
          <div class="form-group"><label class="form-label">Name <span class="required-star">*</span></label><input name="name" value="${escapeHtml(dept.name)}" class="form-control" required /></div>
          <div class="form-group"><label class="form-label">Description</label><textarea name="description" rows="2" class="form-control">${escapeHtml(dept.description || "")}</textarea></div>
        `,
        onSubmit: async (form) => {
          await adminApi.updateDepartment(dept.id, {
            code: form.code,
            name: form.name,
            description: form.description || null,
          });
          showToast("Department updated.", "success");
          renderDepartments(container);
        },
      });
    });
  });

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Department",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Code <span class="required-star">*</span></label><input name="code" class="form-control" placeholder="CSE" required /></div>
        <div class="form-group"><label class="form-label">Name <span class="required-star">*</span></label><input name="name" class="form-control" placeholder="Computer Science" required /></div>
        <div class="form-group"><label class="form-label">Description</label><textarea name="description" rows="2" class="form-control" placeholder="Optional description..."></textarea></div>
      `,
      onSubmit: async (form) => {
        await adminApi.createDepartment({
          ...form,
          description: form.description || null,
        });
        showToast("Department created.", "success");
        renderDepartments(container);
      },
    });
  });
}

function getDefaultIndianAcademicYear() {
  const now = new Date();
  const year = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
  return `${year}-${year + 1}`;
}

function buildSemesterNumberOptions(selected = 1) {
  return Array.from({ length: 10 }, (_, idx) => {
    const num = idx + 1;
    const semType = num % 2 === 1 ? "Odd" : "Even";
    return `<option value="${num}" ${Number(selected) === num ? "selected" : ""}>Semester ${num} (${semType})</option>`;
  }).join("");
}

function validateSemesterFormInputs(form) {
  const yearStr = String(form.academic_year || "").trim();
  const match = yearStr.match(/^(\d{4})-(\d{4})$/);
  if (!match || Number(match[2]) !== Number(match[1]) + 1) {
    throw new Error(
      "Academic year must follow YYYY-YYYY format with consecutive years (e.g. 2026-2027)."
    );
  }
  if (!form.start_date || !form.end_date || form.end_date <= form.start_date) {
    throw new Error("End date must be later than start date.");
  }
  return yearStr;
}

function renderSemesterFormFields(semester = null) {
  const termNumber = semester?.term_number ?? 1;
  const academicYear = semester?.academic_year ?? getDefaultIndianAcademicYear();
  const startDate = semester?.start_date ?? "";
  const endDate = semester?.end_date ?? "";
  const isActive = semester ? Boolean(semester.is_active) : true;
  return `
    <div class="form-group">
      <label class="form-label" for="sem-term-number">Semester Number <span class="required-star">*</span></label>
      <select id="sem-term-number" name="term_number" class="form-control" required>
        ${buildSemesterNumberOptions(termNumber)}
      </select>
      <small class="text-muted">Semester name is generated automatically (e.g. Semester ${escapeHtml(termNumber)}).</small>
    </div>
    <div class="form-group">
      <label class="form-label" for="sem-academic-year">Academic Year <span class="required-star">*</span></label>
      <input
        id="sem-academic-year"
        name="academic_year"
        class="form-control"
        value="${escapeHtml(academicYear)}"
        placeholder="2026-2027"
        pattern="^\\d{4}-\\d{4}$"
        required
      />
      <small class="text-muted">Format: YYYY-YYYY (e.g. 2026-2027).</small>
    </div>
    <div class="form-group">
      <label class="form-label" for="sem-start-date">Start Date <span class="required-star">*</span></label>
      <input id="sem-start-date" name="start_date" type="date" value="${escapeHtml(startDate)}" class="form-control" required />
    </div>
    <div class="form-group">
      <label class="form-label" for="sem-end-date">End Date <span class="required-star">*</span></label>
      <input id="sem-end-date" name="end_date" type="date" value="${escapeHtml(endDate)}" class="form-control" required />
    </div>
    <div class="form-group">
      <label class="form-label" for="sem-status">Status</label>
      <select id="sem-status" name="is_active" class="form-control">
        <option value="true" ${isActive ? "selected" : ""}>Active</option>
        <option value="false" ${!isActive ? "selected" : ""}>Inactive</option>
      </select>
    </div>
  `;
}

async function renderSemesters(container) {
  const data = await adminApi.listSemesters({
    page: state.page,
    page_size: 10,
    search: state.search,
  });
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        ${renderSearchInput({
          id: "entity-search",
          placeholder: "Search semester or academic year...",
          value: state.search,
        })}
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Add Semester</button>
      </div>
      ${renderDataTable({
        columns: [
          { key: "name", label: "Semester" },
          {
            label: "Type",
            render: (r) => {
              const semType =
                r.semester_type || (r.term_number % 2 === 1 ? "Odd" : "Even");
              return renderStatusBadge(
                semType,
                semType === "Odd" ? "info" : "warning"
              );
            },
          },
          { key: "academic_year", label: "Academic Year" },
          { key: "term_number", label: "Sem No" },
          {
            label: "Start Date",
            render: (r) => escapeHtml(formatIndianDate(r.start_date)),
          },
          {
            label: "End Date",
            render: (r) => escapeHtml(formatIndianDate(r.end_date)),
          },
          {
            label: "Status",
            render: (r) =>
              renderStatusBadge(
                r.is_active ? "Active" : "Inactive",
                r.is_active ? "success" : "warning"
              ),
          },
          {
            label: "Action",
            render: (r) =>
              `<div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
                <button class="btn btn-outline btn-sm edit-semester-btn" data-id="${r.id}" type="button">Edit</button>
                <button class="btn btn-outline btn-sm toggle-active-btn" data-id="${r.id}" data-next="${!r.is_active}" type="button">${
                  r.is_active ? "Deactivate" : "Activate"
                }</button>
              </div>`,
          },
        ],
        rows: data.items,
        emptyTitle: "No semesters configured",
      })}
      ${renderPagination(data)}
    </section>
  `;
  document.getElementById("entity-search")?.addEventListener("change", (e) => {
    state.search = e.target.value;
    state.page = 1;
    renderSemesters(container);
  });
  bindPagination(data, () => renderSemesters(container));
  container.querySelectorAll(".toggle-active-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await adminApi.setSemesterActive(btn.dataset.id, btn.dataset.next === "true");
        showToast("Semester updated.", "success");
        renderSemesters(container);
      } catch (err) {
        showToast(err.message || "Failed to update semester.", "error");
        btn.disabled = false;
      }
    });
  });
  container.querySelectorAll(".edit-semester-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sem = data.items.find((item) => String(item.id) === btn.dataset.id);
      if (!sem) return;
      openFormModal({
        title: `Edit ${sem.name} (${sem.academic_year})`,
        fieldsHtml: renderSemesterFormFields(sem),
        onSubmit: async (form) => {
          const academicYear = validateSemesterFormInputs(form);
          const termNumber = Number(form.term_number);
          await adminApi.updateSemester(sem.id, {
            name: `Semester ${termNumber}`,
            academic_year: academicYear,
            term_number: termNumber,
            start_date: form.start_date,
            end_date: form.end_date,
            is_active: form.is_active === "true",
          });
          showToast("Semester updated.", "success");
          renderSemesters(container);
        },
      });
    });
  });

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Semester",
      fieldsHtml: renderSemesterFormFields(),
      onSubmit: async (form) => {
        const academicYear = validateSemesterFormInputs(form);
        const termNumber = Number(form.term_number);
        await adminApi.createSemester({
          academic_year: academicYear,
          term_number: termNumber,
          start_date: form.start_date,
          end_date: form.end_date,
          is_active: form.is_active === "true",
        });
        showToast(`Semester ${termNumber} created.`, "success");
        renderSemesters(container);
      },
    });
  });
}

async function renderCourses(container) {
  const data = await adminApi.listCourses({
    page: state.page,
    page_size: 10,
    search: state.search,
  });
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        ${renderSearchInput({
          id: "entity-search",
          placeholder: "Search course code or title...",
          value: state.search,
        })}
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Add Course</button>
      </div>
      ${renderDataTable({
        columns: [
          { key: "code", label: "Code" },
          { key: "title", label: "Title" },
          { key: "credits", label: "Credits" },
          {
            label: "Department",
            render: (r) => escapeHtml(`${r.department.code} — ${r.department.name}`),
          },
          {
            label: "Action",
            render: (r) =>
              `<button class="btn btn-outline btn-sm edit-course-btn" data-id="${r.id}" type="button">Edit</button>`,
          },
        ],
        rows: data.items,
      })}
      ${renderPagination(data)}
    </section>
  `;
  document.getElementById("entity-search")?.addEventListener("change", (e) => {
    state.search = e.target.value;
    state.page = 1;
    renderCourses(container);
  });
  bindPagination(data, () => renderCourses(container));

  container.querySelectorAll(".edit-course-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const course = data.items.find((c) => String(c.id) === btn.dataset.id);
      if (!course) return;
      openFormModal({
        title: `Edit Course (${course.code})`,
        fieldsHtml: `
          <div class="form-group"><label class="form-label">Code <span class="required-star">*</span></label><input name="code" value="${escapeHtml(course.code)}" class="form-control" required /></div>
          <div class="form-group"><label class="form-label">Title <span class="required-star">*</span></label><input name="title" value="${escapeHtml(course.title)}" class="form-control" required /></div>
          <div class="form-group"><label class="form-label">Credits <span class="required-star">*</span></label><input name="credits" type="number" min="1" value="${escapeHtml(course.credits)}" class="form-control" required /></div>
        `,
        onSubmit: async (form) => {
          await adminApi.updateCourse(course.id, {
            code: form.code,
            title: form.title,
            credits: Number(form.credits),
          });
          showToast("Course updated.", "success");
          renderCourses(container);
        },
      });
    });
  });

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Course",
      fieldsHtml: `
        ${renderSearchableSelectField({
          id: "course-dept-select",
          name: "department_id",
          label: "Department",
          placeholder: "Search department by code or name...",
          required: true,
        })}
        <div class="form-group"><label class="form-label">Code <span class="required-star">*</span></label><input name="code" class="form-control" placeholder="CS101" required /></div>
        <div class="form-group"><label class="form-label">Title <span class="required-star">*</span></label><input name="title" class="form-control" placeholder="Algorithms" required /></div>
        <div class="form-group"><label class="form-label">Credits <span class="required-star">*</span></label><input name="credits" type="number" min="1" value="4" class="form-control" required /></div>
      `,
      onMount: () => [mountDepartmentSelect("course-dept-select")],
      onSubmit: async (form) => {
        await adminApi.createCourse({
          ...form,
          department_id: Number(form.department_id),
          credits: Number(form.credits),
        });
        showToast("Course created.", "success");
        renderCourses(container);
      },
    });
  });
}

async function renderOfferings(container) {
  const data = await adminApi.listOfferings({
    page: state.page,
    page_size: 10,
    search: state.search,
  });
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        ${renderSearchInput({
          id: "entity-search",
          placeholder: "Search course, section, or faculty...",
          value: state.search,
        })}
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Create Offering</button>
      </div>
      ${renderDataTable({
        columns: [
          { label: "Course", render: (r) => escapeHtml(`${r.course.code} — ${r.course.title}`) },
          { label: "Semester", render: (r) => escapeHtml(`${r.semester.name} (${r.semester.academic_year})`) },
          {
            label: "Faculty",
            render: (r) =>
              escapeHtml(`${r.faculty.employee_id} — ${r.faculty.user.full_name}`),
          },
          { key: "section", label: "Section" },
          { label: "Capacity", render: (r) => escapeHtml(r.max_capacity ?? "Unlimited") },
          {
            label: "Status",
            render: (r) =>
              renderStatusBadge(
                r.is_active ? "Active" : "Inactive",
                r.is_active ? "success" : "danger"
              ),
          },
          {
            label: "Action",
            render: (r) =>
              `<button class="btn btn-outline btn-sm toggle-active-btn" data-id="${r.id}" data-next="${!r.is_active}" type="button">${
                r.is_active ? "Deactivate" : "Activate"
              }</button>`,
          },
        ],
        rows: data.items,
      })}
      ${renderPagination(data)}
    </section>
  `;
  document.getElementById("entity-search")?.addEventListener("change", (e) => {
    state.search = e.target.value;
    state.page = 1;
    renderOfferings(container);
  });
  bindPagination(data, () => renderOfferings(container));
  container.querySelectorAll(".toggle-active-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await adminApi.setOfferingActive(btn.dataset.id, btn.dataset.next === "true");
        showToast("Course offering updated.", "success");
        renderOfferings(container);
      } catch (err) {
        showToast(err.message || "Failed to update offering.", "error");
        btn.disabled = false;
      }
    });
  });

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Course Offering",
      fieldsHtml: `
        ${renderSearchableSelectField({
          id: "offering-course-select",
          name: "course_id",
          label: "Course",
          placeholder: "Search course by code or title...",
          required: true,
        })}
        ${renderSearchableSelectField({
          id: "offering-semester-select",
          name: "semester_id",
          label: "Semester",
          placeholder: "Search semester by name or academic year...",
          required: true,
        })}
        ${renderSearchableSelectField({
          id: "offering-faculty-select",
          name: "faculty_id",
          label: "Faculty",
          placeholder: "Search faculty by Employee ID, name, or email...",
          required: true,
        })}
        <div class="form-group"><label class="form-label">Section <span class="required-star">*</span></label><input name="section" value="A" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Max Capacity</label><input name="max_capacity" type="number" min="1" value="60" class="form-control" /></div>
      `,
      onMount: () => [
        mountCourseSelect("offering-course-select"),
        mountSemesterSelect("offering-semester-select"),
        mountFacultySelect("offering-faculty-select"),
      ],
      onSubmit: async (form) => {
        await adminApi.createOffering({
          course_id: Number(form.course_id),
          semester_id: Number(form.semester_id),
          faculty_id: Number(form.faculty_id),
          section: form.section,
          max_capacity: form.max_capacity ? Number(form.max_capacity) : null,
        });
        showToast("Course offering created.", "success");
        renderOfferings(container);
      },
    });
  });
}

async function renderEnrollments(container) {
  const data = await opsApi.listEnrollments({ page: state.page, page_size: 10 });
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">Enrollments</h2>
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Enroll Student</button>
      </div>
      ${renderDataTable({
        columns: [
          {
            label: "Student",
            render: (r) =>
              escapeHtml(`${r.student.roll_number} — ${r.student.user.full_name}`),
          },
          {
            label: "Course",
            render: (r) => escapeHtml(formatOfferingLabel(r.course_offering)),
          },
          {
            label: "Semester",
            render: (r) =>
              escapeHtml(
                `${r.course_offering.semester.name} (${r.course_offering.semester.academic_year})`
              ),
          },
          {
            label: "Enrolled At",
            render: (r) => escapeHtml(formatIndianDateTime(r.enrolled_at)),
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
        emptyTitle: "No enrollments found",
      })}
      ${renderPagination(data)}
    </section>
  `;
  bindPagination(data, () => renderEnrollments(container));

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Enroll Student",
      fieldsHtml: `
        ${renderSearchableSelectField({
          id: "enroll-student-select",
          name: "student_id",
          label: "Student",
          placeholder: "Search student by name, roll number, or email...",
          required: true,
        })}
        ${renderSearchableSelectField({
          id: "enroll-offering-select",
          name: "course_offering_id",
          label: "Course Offering",
          placeholder: "Search offering by course code, semester, section, or faculty...",
          required: true,
        })}
      `,
      onMount: () => [
        mountStudentSelect("enroll-student-select"),
        mountOfferingSelect("enroll-offering-select"),
      ],
      onSubmit: async (form) => {
        await opsApi.enrollStudent({
          student_id: Number(form.student_id),
          course_offering_id: Number(form.course_offering_id),
        });
        showToast("Student enrolled.", "success");
        renderEnrollments(container);
      },
    });
  });
}

async function renderNotices(container) {
  const data = await opsApi.listNotices({ page: state.page, page_size: 10 });
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">Notices</h2>
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Publish Notice</button>
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
                ? `<button class="btn btn-outline btn-sm deact-notice-btn" data-id="${r.id}" type="button">Deactivate</button>`
                : "—",
          },
        ],
        rows: data.items,
        emptyTitle: "No notices published",
      })}
      ${renderPagination(data)}
    </section>
  `;
  bindPagination(data, () => renderNotices(container));
  container.querySelectorAll(".deact-notice-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await opsApi.deactivateNotice(btn.dataset.id);
        showToast("Notice deactivated.", "success");
        renderNotices(container);
      } catch (err) {
        showToast(err.message || "Failed to deactivate notice.", "error");
        btn.disabled = false;
      }
    });
  });

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Publish Notice",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Title <span class="required-star">*</span></label><input name="title" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Body <span class="required-star">*</span></label><textarea name="body" rows="3" class="form-control" required></textarea></div>
        <div class="form-group"><label class="form-label">Target Role (optional)</label>
          <select name="target_role" class="form-control">
            <option value="">All Roles</option>
            <option value="student">Students</option>
            <option value="faculty">Faculty</option>
          </select>
        </div>
      `,
      onSubmit: async (form) => {
        await opsApi.createNotice({
          title: form.title,
          body: form.body,
          targets: form.target_role ? [{ target_role: form.target_role }] : [],
        });
        showToast("Notice published.", "success");
        renderNotices(container);
      },
    });
  });
}

async function renderTimetable(container) {
  const data = await opsApi.listTimetable({ page: state.page, page_size: 20 });
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">Timetable Slots</h2>
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Add Slot</button>
      </div>
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
          {
            label: "Action",
            render: (r) =>
              `<button class="btn btn-danger btn-sm del-slot-btn" data-id="${r.id}" type="button">Delete</button>`,
          },
        ],
        rows: data.items,
        emptyTitle: "No timetable slots configured",
      })}
      ${renderPagination(data)}
    </section>
  `;
  bindPagination(data, () => renderTimetable(container));
  container.querySelectorAll(".del-slot-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await opsApi.deleteTimetableSlot(btn.dataset.id);
        showToast("Slot deleted.", "success");
        renderTimetable(container);
      } catch (err) {
        showToast(err.message || "Failed to delete slot.", "error");
        btn.disabled = false;
      }
    });
  });

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Timetable Slot",
      fieldsHtml: `
        ${renderSearchableSelectField({
          id: "timetable-offering-select",
          name: "course_offering_id",
          label: "Course Offering",
          placeholder: "Search offering by course code, semester, section, or faculty...",
          required: true,
        })}
        <div class="form-group"><label class="form-label">Day <span class="required-star">*</span></label>
          <select name="day_of_week" class="form-control">
            <option value="monday">Monday</option><option value="tuesday">Tuesday</option>
            <option value="wednesday">Wednesday</option><option value="thursday">Thursday</option>
            <option value="friday">Friday</option><option value="saturday">Saturday</option>
          </select>
        </div>
        <div class="form-group"><label class="form-label">Start Time <span class="required-star">*</span></label><input name="start_time" type="time" value="09:00" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">End Time <span class="required-star">*</span></label><input name="end_time" type="time" value="10:00" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Room</label><input name="room" class="form-control" placeholder="Room 101" /></div>
      `,
      onMount: () => [mountOfferingSelect("timetable-offering-select")],
      onSubmit: async (form) => {
        await opsApi.createTimetableSlot({
          ...form,
          course_offering_id: Number(form.course_offering_id),
        });
        showToast("Timetable slot created.", "success");
        renderTimetable(container);
      },
    });
  });
}

async function renderOfferingLookupSection(container, { title, mode }) {
  const offerings = await adminApi.listOfferings({ page: 1, page_size: 50 });
  const optionsHtml = offerings.items
    .map(
      (o) =>
        `<option value="${o.id}">${escapeHtml(`${formatOfferingLabel(o)} • ${o.semester.name}`)}</option>`
    )
    .join("");

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">${escapeHtml(title)}</h2>
        <select id="admin-offering-select" class="form-control" style="max-width:360px;" aria-label="Select course offering">
          ${optionsHtml || '<option value="">No offerings found</option>'}
        </select>
      </div>
      <div id="offering-sub-content"></div>
    </section>
  `;

  const select = document.getElementById("admin-offering-select");
  const sub = document.getElementById("offering-sub-content");

  async function load() {
    if (!select.value) {
      sub.innerHTML = "";
      return;
    }
    sub.innerHTML = renderLoading();
    try {
      if (mode === "attendance") {
        const data = await opsApi.listOfferingSessions(select.value);
        sub.innerHTML = renderDataTable({
          columns: [
            { label: "Date", render: (r) => escapeHtml(formatIndianDate(r.session_date)) },
            { label: "Session", render: (r) => escapeHtml(`Session #${r.session_number}`) },
            { key: "topic", label: "Topic" },
            { label: "Marked", render: (r) => escapeHtml(`${r.records.length} student(s)`) },
          ],
          rows: data.items,
          emptyTitle: "No attendance sessions recorded",
        });
      } else {
        const data = await opsApi.listOfferingAssignments(select.value);
        sub.innerHTML = renderDataTable({
          columns: [
            { key: "title", label: "Title" },
            {
              label: "Course",
              render: (r) => escapeHtml(formatOfferingLabel(r.course_offering)),
            },
            { label: "Due At", render: (r) => escapeHtml(formatIndianDateTime(r.due_at)) },
            { key: "max_score", label: "Max Score" },
          ],
          rows: data.items,
          emptyTitle: "No assignments published",
        });
      }
    } catch (err) {
      sub.innerHTML = renderErrorState(err.message || "Failed to load data.");
    }
  }

  select.addEventListener("change", load);
  await load();
}

export async function renderAdminPage(container, routeId) {
  state.page = 1;
  state.search = "";
  state.showArchived = false;
  container.innerHTML = renderLoading("Loading module...");
  try {
    switch (routeId) {
      case "dashboard":
        await renderAdminOverview(container);
        break;
      case "students":
        await renderStudents(container);
        break;
      case "faculty":
        await renderFaculty(container);
        break;
      case "departments":
        await renderDepartments(container);
        break;
      case "semesters":
        await renderSemesters(container);
        break;
      case "courses":
        await renderCourses(container);
        break;
      case "offerings":
        await renderOfferings(container);
        break;
      case "enrollments":
        await renderEnrollments(container);
        break;
      case "attendance":
        await renderOfferingLookupSection(container, {
          title: "Attendance Overview",
          mode: "attendance",
        });
        break;
      case "assignments":
        await renderOfferingLookupSection(container, {
          title: "Assignments Overview",
          mode: "assignments",
        });
        break;
      case "notices":
        await renderNotices(container);
        break;
      case "timetable":
        await renderTimetable(container);
        break;
      default:
        await renderAdminOverview(container);
    }
  } catch (err) {
    container.innerHTML = renderErrorState(err.message || "Failed to load data.");
  }
}
