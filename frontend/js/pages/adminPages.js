import * as adminApi from "../api/adminApi.js";
import * as opsApi from "../api/operationsApi.js";
import { renderDataTable } from "../components/dataTable.js";
import { closeModal, openModal } from "../components/modal.js";
import { renderPagination } from "../components/pagination.js";
import { showToast } from "../components/toast.js";
import {
  escapeHtml,
  renderErrorState,
  renderLoading,
  renderSearchInput,
  renderStatusBadge,
} from "../components/ui.js";

const state = {
  page: 1,
  search: "",
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

function openFormModal({ title, fieldsHtml, onSubmit }) {
  openModal({
    title,
    bodyHtml: `<form id="modal-entity-form">${fieldsHtml}<button class="btn btn-primary btn-block" type="submit">Save</button></form>`,
  });
  document
    .getElementById("modal-entity-form")
    ?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = new FormData(e.target);
      try {
        await onSubmit(Object.fromEntries(formData.entries()));
        closeModal();
      } catch (err) {
        showToast(err.message || "Operation failed.", "error");
      }
    });
}

async function renderAdminOverview(container) {
  const [students, faculty, depts, sems, courses, offerings] =
    await Promise.all([
      adminApi.listStudents({ page: 1, page_size: 1 }),
      adminApi.listFaculty({ page: 1, page_size: 1 }),
      adminApi.listDepartments({ page: 1, page_size: 1 }),
      adminApi.listSemesters({ page: 1, page_size: 1 }),
      adminApi.listCourses({ page: 1, page_size: 1 }),
      adminApi.listOfferings({ page: 1, page_size: 1 }),
    ]);

  const cards = [
    ["Students", students.total],
    ["Faculty", faculty.total],
    ["Departments", depts.total],
    ["Semesters", sems.total],
    ["Courses", courses.total],
    ["Course Offerings", offerings.total],
  ];

  container.innerHTML = `
    <section class="stats-grid">
      ${cards
        .map(
          ([label, val]) => `
        <div class="stat-card">
          <div class="text-muted">${escapeHtml(label)}</div>
          <div class="stat-value">${escapeHtml(val)}</div>
        </div>`
        )
        .join("")}
    </section>
    <section class="card">
      <h2 class="card-title">System Administration</h2>
      <p class="text-muted" style="margin-top:0.5rem;">
        Use the sidebar to manage students, faculty, academic structure, enrollments, notices, and timetable slots.
      </p>
    </section>
  `;
}

async function renderStudents(container) {
  const data = await adminApi.listStudents({
    page: state.page,
    page_size: 10,
    search: state.search,
  });

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        ${renderSearchInput({
          id: "entity-search",
          placeholder: "Search name, email, roll...",
          value: state.search,
        })}
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Add Student</button>
      </div>
      ${renderDataTable({
        columns: [
          { key: "roll_number", label: "Roll No" },
          { label: "Name", render: (r) => escapeHtml(r.user.full_name) },
          { label: "Email", render: (r) => escapeHtml(r.user.email) },
          { label: "Department", render: (r) => escapeHtml(r.department.code) },
          { key: "current_semester_number", label: "Sem" },
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
              `<button class="btn btn-outline btn-sm toggle-active-btn" data-id="${r.id}" data-next="${!r.user.is_active}" type="button">${
                r.user.is_active ? "Deactivate" : "Activate"
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
    renderStudents(container);
  });

  bindPagination(data, () => renderStudents(container));

  container.querySelectorAll(".toggle-active-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await adminApi.setStudentActive(
        btn.dataset.id,
        btn.dataset.next === "true"
      );
      showToast("Student status updated.", "success");
      renderStudents(container);
    });
  });

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Student",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Full Name</label><input name="full_name" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Email</label><input name="email" type="email" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Password</label><input name="password" type="password" class="form-control" placeholder="Min 8 chars, Aa1!" required /></div>
        <div class="form-group"><label class="form-label">Department ID</label><input name="department_id" type="number" min="1" value="1" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Roll Number</label><input name="roll_number" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Admission Year</label><input name="admission_year" type="number" value="2026" class="form-control" required /></div>
      `,
      onSubmit: async (form) => {
        await adminApi.createStudent({
          ...form,
          department_id: Number(form.department_id),
          admission_year: Number(form.admission_year),
        });
        showToast("Student created.", "success");
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
          placeholder: "Search name, email, emp ID...",
          value: state.search,
        })}
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Add Faculty</button>
      </div>
      ${renderDataTable({
        columns: [
          { key: "employee_id", label: "Emp ID" },
          { label: "Name", render: (r) => escapeHtml(r.user.full_name) },
          { label: "Email", render: (r) => escapeHtml(r.user.email) },
          { key: "designation", label: "Designation" },
          { label: "Dept", render: (r) => escapeHtml(r.department.code) },
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
              `<button class="btn btn-outline btn-sm toggle-active-btn" data-id="${r.id}" data-next="${!r.user.is_active}" type="button">${
                r.user.is_active ? "Deactivate" : "Activate"
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
    renderFaculty(container);
  });
  bindPagination(data, () => renderFaculty(container));
  container.querySelectorAll(".toggle-active-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await adminApi.setFacultyActive(
        btn.dataset.id,
        btn.dataset.next === "true"
      );
      showToast("Faculty status updated.", "success");
      renderFaculty(container);
    });
  });

  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Faculty",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Full Name</label><input name="full_name" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Email</label><input name="email" type="email" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Password</label><input name="password" type="password" class="form-control" placeholder="Min 8 chars, Aa1!" required /></div>
        <div class="form-group"><label class="form-label">Department ID</label><input name="department_id" type="number" min="1" value="1" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Employee ID</label><input name="employee_id" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Designation</label><input name="designation" class="form-control" required /></div>
      `,
      onSubmit: async (form) => {
        await adminApi.createFaculty({
          ...form,
          department_id: Number(form.department_id),
        });
        showToast("Faculty created.", "success");
        renderFaculty(container);
      },
    });
  });
}

async function renderDepartments(container) {
  const data = await adminApi.listDepartments({ page: state.page, page_size: 10 });
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">Departments</h2>
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Add Department</button>
      </div>
      ${renderDataTable({
        columns: [
          { key: "id", label: "ID" },
          { key: "code", label: "Code" },
          { key: "name", label: "Name" },
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
  bindPagination(data, () => renderDepartments(container));
  container.querySelectorAll(".toggle-active-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await adminApi.setDepartmentActive(btn.dataset.id, btn.dataset.next === "true");
      showToast("Department updated.", "success");
      renderDepartments(container);
    });
  });
  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Department",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Code</label><input name="code" class="form-control" placeholder="CSE" required /></div>
        <div class="form-group"><label class="form-label">Name</label><input name="name" class="form-control" placeholder="Computer Science" required /></div>
      `,
      onSubmit: async (form) => {
        await adminApi.createDepartment(form);
        showToast("Department created.", "success");
        renderDepartments(container);
      },
    });
  });
}

async function renderSemesters(container) {
  const data = await adminApi.listSemesters({ page: state.page, page_size: 10 });
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">Semesters</h2>
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Add Semester</button>
      </div>
      ${renderDataTable({
        columns: [
          { key: "id", label: "ID" },
          { key: "name", label: "Name" },
          { key: "academic_year", label: "Academic Year" },
          { key: "term_number", label: "Term" },
          { key: "start_date", label: "Start" },
          { key: "end_date", label: "End" },
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
  bindPagination(data, () => renderSemesters(container));
  container.querySelectorAll(".toggle-active-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await adminApi.setSemesterActive(btn.dataset.id, btn.dataset.next === "true");
      showToast("Semester updated.", "success");
      renderSemesters(container);
    });
  });
  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Semester",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Name</label><input name="name" class="form-control" placeholder="Fall 2026" required /></div>
        <div class="form-group"><label class="form-label">Academic Year</label><input name="academic_year" class="form-control" placeholder="2026-2027" required /></div>
        <div class="form-group"><label class="form-label">Term Number</label><input name="term_number" type="number" value="1" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Start Date</label><input name="start_date" type="date" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">End Date</label><input name="end_date" type="date" class="form-control" required /></div>
      `,
      onSubmit: async (form) => {
        await adminApi.createSemester({
          ...form,
          term_number: Number(form.term_number),
          is_active: true,
        });
        showToast("Semester created.", "success");
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
          { key: "id", label: "ID" },
          { key: "code", label: "Code" },
          { key: "title", label: "Title" },
          { key: "credits", label: "Credits" },
          { label: "Department", render: (r) => escapeHtml(r.department.code) },
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
  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Course",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Department ID</label><input name="department_id" type="number" value="1" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Code</label><input name="code" class="form-control" placeholder="CS101" required /></div>
        <div class="form-group"><label class="form-label">Title</label><input name="title" class="form-control" placeholder="Algorithms" required /></div>
        <div class="form-group"><label class="form-label">Credits</label><input name="credits" type="number" min="1" value="4" class="form-control" required /></div>
      `,
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
  const data = await adminApi.listOfferings({ page: state.page, page_size: 10 });
  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">Course Offerings</h2>
        <button id="add-entity-btn" class="btn btn-primary btn-sm" type="button">+ Create Offering</button>
      </div>
      ${renderDataTable({
        columns: [
          { key: "id", label: "ID" },
          { label: "Course", render: (r) => escapeHtml(`${r.course.code} — ${r.course.title}`) },
          { label: "Semester", render: (r) => escapeHtml(r.semester.name) },
          { label: "Faculty", render: (r) => escapeHtml(r.faculty.user.full_name) },
          { key: "section", label: "Sec" },
          {
            label: "Status",
            render: (r) =>
              renderStatusBadge(
                r.is_active ? "Active" : "Inactive",
                r.is_active ? "success" : "danger"
              ),
          },
        ],
        rows: data.items,
      })}
      ${renderPagination(data)}
    </section>
  `;
  bindPagination(data, () => renderOfferings(container));
  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Course Offering",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Course ID</label><input name="course_id" type="number" value="1" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Semester ID</label><input name="semester_id" type="number" value="1" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Faculty ID</label><input name="faculty_id" type="number" value="1" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Section</label><input name="section" value="A" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Max Capacity</label><input name="max_capacity" type="number" value="60" class="form-control" /></div>
      `,
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
          { key: "id", label: "ID" },
          { label: "Student", render: (r) => escapeHtml(`${r.student.roll_number} (${r.student.user.full_name})`) },
          { label: "Course", render: (r) => escapeHtml(`${r.course_offering.course.code} (${r.course_offering.section})`) },
          {
            label: "Status",
            render: (r) => renderStatusBadge(r.status, r.status === "enrolled" ? "success" : "warning"),
          },
        ],
        rows: data.items,
      })}
      ${renderPagination(data)}
    </section>
  `;
  bindPagination(data, () => renderEnrollments(container));
  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Enroll Student",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Student ID</label><input name="student_id" type="number" min="1" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Course Offering ID</label><input name="course_offering_id" type="number" min="1" class="form-control" required /></div>
      `,
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
          { key: "id", label: "ID" },
          { key: "title", label: "Title" },
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
      })}
      ${renderPagination(data)}
    </section>
  `;
  bindPagination(data, () => renderNotices(container));
  container.querySelectorAll(".deact-notice-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await opsApi.deactivateNotice(btn.dataset.id);
      showToast("Notice deactivated.", "success");
      renderNotices(container);
    });
  });
  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Publish Notice",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Title</label><input name="title" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Body</label><textarea name="body" rows="3" class="form-control" required></textarea></div>
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
          { key: "id", label: "ID" },
          { key: "course_offering_id", label: "Offering ID" },
          { key: "day_of_week", label: "Day" },
          { key: "start_time", label: "Start" },
          { key: "end_time", label: "End" },
          { key: "room", label: "Room" },
          {
            label: "Action",
            render: (r) =>
              `<button class="btn btn-danger btn-sm del-slot-btn" data-id="${r.id}" type="button">Delete</button>`,
          },
        ],
        rows: data.items,
      })}
      ${renderPagination(data)}
    </section>
  `;
  bindPagination(data, () => renderTimetable(container));
  container.querySelectorAll(".del-slot-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await opsApi.deleteTimetableSlot(btn.dataset.id);
      showToast("Slot deleted.", "success");
      renderTimetable(container);
    });
  });
  document.getElementById("add-entity-btn")?.addEventListener("click", () => {
    openFormModal({
      title: "Create Timetable Slot",
      fieldsHtml: `
        <div class="form-group"><label class="form-label">Course Offering ID</label><input name="course_offering_id" type="number" min="1" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Day</label>
          <select name="day_of_week" class="form-control">
            <option value="monday">Monday</option><option value="tuesday">Tuesday</option>
            <option value="wednesday">Wednesday</option><option value="thursday">Thursday</option>
            <option value="friday">Friday</option><option value="saturday">Saturday</option>
          </select>
        </div>
        <div class="form-group"><label class="form-label">Start Time</label><input name="start_time" type="time" value="09:00" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">End Time</label><input name="end_time" type="time" value="10:00" class="form-control" required /></div>
        <div class="form-group"><label class="form-label">Room</label><input name="room" class="form-control" placeholder="Room 101" /></div>
      `,
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
        `<option value="${o.id}">${escapeHtml(`${o.course.code} (${o.section}) — ${o.semester.name}`)}</option>`
    )
    .join("");

  container.innerHTML = `
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">${escapeHtml(title)}</h2>
        <select id="admin-offering-select" class="form-control" style="max-width:320px;">
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
    if (mode === "attendance") {
      const data = await opsApi.listOfferingSessions(select.value);
      sub.innerHTML = renderDataTable({
        columns: [
          { key: "id", label: "Session ID" },
          { key: "session_date", label: "Date" },
          { key: "session_number", label: "#" },
          { key: "topic", label: "Topic" },
          { label: "Records", render: (r) => escapeHtml(r.records.length) },
        ],
        rows: data.items,
      });
    } else {
      const data = await opsApi.listOfferingAssignments(select.value);
      sub.innerHTML = renderDataTable({
        columns: [
          { key: "id", label: "ID" },
          { key: "title", label: "Title" },
          { key: "due_at", label: "Due At" },
          { key: "max_score", label: "Max Score" },
        ],
        rows: data.items,
      });
    }
  }

  select.addEventListener("change", load);
  await load();
}

export async function renderAdminPage(container, routeId) {
  state.page = 1;
  state.search = "";
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
