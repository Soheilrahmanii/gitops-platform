{{/*
Full name: prefer .Release.Name since the IDP names releases after the resource
(e.g. "platform-hello-world"), which is already unique cluster-wide.
*/}}
{{- define "app-template.fullname" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Chart label — used to track which chart version deployed this release.
*/}}
{{- define "app-template.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource so kubectl and ArgoCD can identify them.
*/}}
{{- define "app-template.labels" -}}
helm.sh/chart: {{ include "app-template.chart" . }}
{{ include "app-template.selectorLabels" . }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels — stable subset used by Service and Deployment matchLabels.
Must NOT change after first deploy (a change would break rolling updates).
*/}}
{{- define "app-template.selectorLabels" -}}
app.kubernetes.io/name: {{ include "app-template.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
ServiceAccount name: use the explicit override, fall back to the release name
(which matches the SA that Terraform created in this namespace).
*/}}
{{- define "app-template.serviceAccountName" -}}
{{- if .Values.serviceAccount.name }}
{{- .Values.serviceAccount.name }}
{{- else }}
{{- include "app-template.fullname" . }}
{{- end }}
{{- end }}
