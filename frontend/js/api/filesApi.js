import { CONFIG } from "../config.js";
import { ApiError, apiRequest, getStoredToken } from "./client.js";

export function uploadWithProgress(path, formData, onProgress = null) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${CONFIG.API_BASE_URL}${path}`);

    const token = getStoredToken();
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }
    xhr.setRequestHeader("Accept", "application/json");
    xhr.timeout = CONFIG.REQUEST_TIMEOUT_MS;

    if (onProgress && xhr.upload) {
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });
    }

    xhr.onload = () => {
      let data = null;
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        data = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
      } else {
        const detail =
          (data && (data.detail || data.message)) ||
          `Upload failed with status ${xhr.status}.`;
        reject(new ApiError(String(detail), xhr.status, data));
      }
    };

    xhr.onerror = () =>
      reject(new ApiError("Network error during file upload.", 0));
    xhr.ontimeout = () =>
      reject(new ApiError("File upload timed out.", 0));

    xhr.send(formData);
  });
}

export const uploadAssignmentAttachment = (assignmentId, formData, onProgress) =>
  uploadWithProgress(`/assignments/${assignmentId}/attachments`, formData, onProgress);

export const listAssignmentAttachments = (assignmentId) =>
  apiRequest(`/assignments/${assignmentId}/attachments`);

export const uploadSubmissionFile = (submissionId, formData, onProgress) =>
  uploadWithProgress(`/submissions/${submissionId}/files`, formData, onProgress);

export const listSubmissionFiles = (submissionId) =>
  apiRequest(`/submissions/${submissionId}/files`);

export const getFileDownload = (fileId) => apiRequest(`/files/${fileId}`);

export const deleteFile = (fileId) =>
  apiRequest(`/files/${fileId}`, { method: "DELETE" });
