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

// Self-Service Profiles
export const getMyStudentProfile = () => apiRequest("/students/me");
export const getMyFacultyProfile = () => apiRequest("/faculty/me");
export const getMyFacultyOfferings = (params) =>
  apiRequest(`/faculty/me/course-offerings${toQuery(params)}`);

// Enrollments
export const listEnrollments = (params) =>
  apiRequest(`/enrollments${toQuery(params)}`);
export const enrollStudent = (body) =>
  apiRequest("/enrollments", { method: "POST", body });
export const updateEnrollmentStatus = (id, status) =>
  apiRequest(`/enrollments/${id}`, { method: "PATCH", body: { status } });
export const listMyEnrollments = (params) =>
  apiRequest(`/enrollments/me${toQuery(params)}`);
export const listOfferingEnrollments = (offeringId, params) =>
  apiRequest(`/enrollments/offerings/${offeringId}${toQuery(params)}`);

// Attendance
export const createAttendanceSession = (body) =>
  apiRequest("/attendance/sessions", { method: "POST", body });
export const listOfferingSessions = (offeringId, params) =>
  apiRequest(`/attendance/offerings/${offeringId}/sessions${toQuery(params)}`);
export const markAttendanceRecords = (sessionId, records) =>
  apiRequest(`/attendance/sessions/${sessionId}/records`, {
    method: "PUT",
    body: { records },
  });
export const getMyAttendance = (params) =>
  apiRequest(`/attendance/me${toQuery(params)}`);

// Assignments & Submissions
export const createAssignment = (body) =>
  apiRequest("/assignments", { method: "POST", body });
export const updateAssignment = (id, body) =>
  apiRequest(`/assignments/${id}`, { method: "PATCH", body });
export const listOfferingAssignments = (offeringId, params) =>
  apiRequest(`/assignments/offerings/${offeringId}${toQuery(params)}`);
export const submitAssignment = (assignmentId, body) =>
  apiRequest(`/assignments/${assignmentId}/submissions`, {
    method: "POST",
    body,
  });
export const listAssignmentSubmissions = (assignmentId, params) =>
  apiRequest(`/assignments/${assignmentId}/submissions${toQuery(params)}`);
export const listMySubmissions = (params) =>
  apiRequest(`/submissions/me${toQuery(params)}`);
export const gradeSubmission = (submissionId, body) =>
  apiRequest(`/submissions/${submissionId}/grade`, { method: "PATCH", body });

// Notices
export const listNotices = (params) => apiRequest(`/notices${toQuery(params)}`);
export const createNotice = (body) =>
  apiRequest("/notices", { method: "POST", body });
export const updateNotice = (id, body) =>
  apiRequest(`/notices/${id}`, { method: "PATCH", body });
export const deactivateNotice = (id) =>
  apiRequest(`/notices/${id}/deactivate`, { method: "PATCH" });

// Timetable
export const listTimetable = (params) =>
  apiRequest(`/timetable${toQuery(params)}`);
export const createTimetableSlot = (body) =>
  apiRequest("/timetable", { method: "POST", body });
export const updateTimetableSlot = (id, body) =>
  apiRequest(`/timetable/${id}`, { method: "PATCH", body });
export const deleteTimetableSlot = (id) =>
  apiRequest(`/timetable/${id}`, { method: "DELETE" });
export const getMyTimetable = (params) =>
  apiRequest(`/timetable/me${toQuery(params)}`);
