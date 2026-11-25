const runtimeConfig =
  (typeof window !== "undefined" && window.CMS_CONFIG) || {};

export const CONFIG = Object.freeze({
  APP_NAME: "College Management System",
  API_BASE_URL:
    runtimeConfig.API_BASE_URL || "http://127.0.0.1:8000/api/v1",
  REQUEST_TIMEOUT_MS: 15000,
  TOKEN_STORAGE_KEY: "cms_access_token",
  USER_STORAGE_KEY: "cms_current_user",
});

export const ROLES = Object.freeze({
  ADMIN: "admin",
  FACULTY: "faculty",
  STUDENT: "student",
});

export const ROLE_NAVIGATION = Object.freeze({
  [ROLES.ADMIN]: [
    { id: "dashboard", label: "Dashboard", icon: "layoutDashboard" },
    { id: "students", label: "Students", icon: "users" },
    { id: "faculty", label: "Faculty", icon: "userCheck" },
    { id: "departments", label: "Departments", icon: "building" },
    { id: "semesters", label: "Semesters", icon: "calendar" },
    { id: "courses", label: "Courses", icon: "bookOpen" },
    { id: "offerings", label: "Course Offerings", icon: "layers" },
    { id: "enrollments", label: "Enrollments", icon: "clipboardList" },
    { id: "attendance", label: "Attendance Overview", icon: "checkSquare" },
    { id: "assignments", label: "Assignments", icon: "fileText" },
    { id: "notices", label: "Notices", icon: "bell" },
    { id: "timetable", label: "Timetable", icon: "clock" },
  ],
  [ROLES.FACULTY]: [
    { id: "dashboard", label: "Dashboard", icon: "layoutDashboard" },
    { id: "profile", label: "My Profile", icon: "user" },
    { id: "offerings", label: "My Course Offerings", icon: "layers" },
    { id: "students", label: "Offering Students", icon: "users" },
    { id: "attendance", label: "Attendance", icon: "checkSquare" },
    { id: "assignments", label: "Assignments", icon: "fileText" },
    { id: "submissions", label: "Submission Evaluation", icon: "award" },
    { id: "notices", label: "Notices", icon: "bell" },
    { id: "timetable", label: "Timetable", icon: "clock" },
  ],
  [ROLES.STUDENT]: [
    { id: "dashboard", label: "Dashboard", icon: "layoutDashboard" },
    { id: "profile", label: "My Profile", icon: "user" },
    { id: "courses", label: "My Courses", icon: "bookOpen" },
    { id: "attendance", label: "My Attendance", icon: "checkSquare" },
    { id: "assignments", label: "My Assignments", icon: "fileText" },
    { id: "submissions", label: "My Submissions", icon: "upload" },
    { id: "notices", label: "Notices", icon: "bell" },
    { id: "timetable", label: "My Timetable", icon: "clock" },
  ],
});
