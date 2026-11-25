import { apiRequest } from "./client.js";

function toQuery(params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      qs.set(k, String(v));
    }
  });
  const str = qs.toString();
  return str ? `?${str}` : "";
}

// Students
export const listStudents = (params) =>
  apiRequest(`/admin/students${toQuery(params)}`);
export const getStudent = (id) => apiRequest(`/admin/students/${id}`);
export const createStudent = (body) =>
  apiRequest("/admin/students", { method: "POST", body });
export const updateStudent = (id, body) =>
  apiRequest(`/admin/students/${id}`, { method: "PATCH", body });
export const setStudentActive = (id, active) =>
  apiRequest(`/admin/students/${id}/${active ? "activate" : "deactivate"}`, {
    method: "PATCH",
  });

// Faculty
export const listFaculty = (params) =>
  apiRequest(`/admin/faculty${toQuery(params)}`);
export const getFaculty = (id) => apiRequest(`/admin/faculty/${id}`);
export const createFaculty = (body) =>
  apiRequest("/admin/faculty", { method: "POST", body });
export const updateFaculty = (id, body) =>
  apiRequest(`/admin/faculty/${id}`, { method: "PATCH", body });
export const setFacultyActive = (id, active) =>
  apiRequest(`/admin/faculty/${id}/${active ? "activate" : "deactivate"}`, {
    method: "PATCH",
  });

// Departments
export const listDepartments = (params) =>
  apiRequest(`/admin/departments${toQuery(params)}`);
export const createDepartment = (body) =>
  apiRequest("/admin/departments", { method: "POST", body });
export const updateDepartment = (id, body) =>
  apiRequest(`/admin/departments/${id}`, { method: "PATCH", body });
export const setDepartmentActive = (id, active) =>
  apiRequest(`/admin/departments/${id}/${active ? "activate" : "deactivate"}`, {
    method: "PATCH",
  });

// Semesters
export const listSemesters = (params) =>
  apiRequest(`/admin/semesters${toQuery(params)}`);
export const createSemester = (body) =>
  apiRequest("/admin/semesters", { method: "POST", body });
export const updateSemester = (id, body) =>
  apiRequest(`/admin/semesters/${id}`, { method: "PATCH", body });
export const setSemesterActive = (id, active) =>
  apiRequest(`/admin/semesters/${id}/${active ? "activate" : "deactivate"}`, {
    method: "PATCH",
  });

// Courses
export const listCourses = (params) =>
  apiRequest(`/admin/courses${toQuery(params)}`);
export const createCourse = (body) =>
  apiRequest("/admin/courses", { method: "POST", body });
export const updateCourse = (id, body) =>
  apiRequest(`/admin/courses/${id}`, { method: "PATCH", body });

// Course Offerings
export const listOfferings = (params) =>
  apiRequest(`/admin/course-offerings${toQuery(params)}`);
export const createOffering = (body) =>
  apiRequest("/admin/course-offerings", { method: "POST", body });
export const updateOffering = (id, body) =>
  apiRequest(`/admin/course-offerings/${id}`, { method: "PATCH", body });
export const setOfferingActive = (id, active) =>
  apiRequest(
    `/admin/course-offerings/${id}/${active ? "activate" : "deactivate"}`,
    { method: "PATCH" }
  );
