<template>
  <div>
    <div class="col-12 fw-bolder text-end">Count : {{ courses.length }}</div>
    <fieldset class="border p-2 form-group ms-2 mb-2" style="line-height: 70%;">
      <legend class="float-none px-2 font-12 mb-0 w-auto">Search Filter :</legend>
      <div class="d-flex flex-row justify-content-start">
        <input class="form-control form-control-sm search-input" type="search" v-model="search_filter" placeholder="Search by college code" aria-label=" search applicants">
      </div>
    </fieldset>
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
      <div class="mt-2 text-muted">Loading courses...</div>
    </div>
    <div v-else-if="courses.length === 0" class="text-center text-muted py-5">
      No courses found.
    </div>
    <div class="row g-3">
      <div class="col-12 col-sm-4 col-lg-3" v-for="(c, idx) in orderedCourses" :key="idx">
        <div class="card h-100 shadow-sm">
          <div class="card-header bg-light">
            <div class="d-flex align-items-center justify-content-between">
              <div class="d-flex align-items-center gap-2 text-truncate">
                <span class="small text-muted">{{ c.college_code }}</span>
                <span class="fw-semibold text-truncate">{{ c.college_name }}</span>
              </div>
              <span :class="{'badge bg-success': c.status === 'RF', 'badge bg-danger': c.status === 'RT'}">{{ c.status }}</span>
            </div>
          </div>

          <div class="card-body">
            <div class="d-flex justify-content-between">
              <div class="small text-muted">Transfer</div>
              <div class="fw-semibold">{{ c.trans_subj }}-{{ c.trans_numb }}</div>
            </div>
            <div class="d-flex justify-content-between mt-1">
              <div class="small text-muted">Institution</div>
              <div class="fw-semibold">{{ c.inst_subj }}-{{ c.inst_numb }}</div>
            </div>
            <button class="btn btn-outline-secondary btn-sm w-100" @click="openDetails(c)">
              {{ c._details ? 'Hide' : 'View' }} Evaluator Details
            </button>
            <div v-if="c._details" class="mt-2 d-flex justify-content-between">
              <div v-if="c._details?.assigned_evaluator">
                <div class="small text-muted">Evaluators</div>
                <div class="d-flex flex-column gap-2 mb-2">
                  <div v-for="(ev, index) in c._details.evaluators" :key="ev" class="d-flex">
                    <span class="badge bg-success">{{ ev }}</span>
                    <span v-if="c._details.evaluators_names[index]" class="badge bg-secondary">
                      {{ c._details.evaluators_names[index]?.EVALUATOR_NAME }}
                    </span>
                  </div>
                </div>
                <div class="small text-muted">Evaluator's Department and College</div>
                <div>{{ c._details.assigned_dept_code }} - {{ c._details.assigned_dept_desc }}</div>
                <div>{{ c._details.assigned_coll_code }} - {{ c._details.assigned_coll_desc }}</div>
              </div>
              <div v-else>ADD EVALUATOR in Department Config</div>
              <div v-if="c._details" @click="openEditor(c)">Edit</div>
            </div>
            <div v-if="c.filename" class="mt-3">
              <div class="d-flex align-items-center">
                <div class="me-1 text-secondary">
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M19.903 8.586a.997.997 0 0 0-.196-.293l-6-6a.997.997 0 0 0-.293-.196c-.03-.014-.062-.022-.094-.033a.991.991 0 0 0-.259-.051C13.04 2.011 13.021 2 13 2H6c-1.103 0-2 .897-2 2v16c0 1.103.897 2 2 2h12c1.103 0 2-.897 2-2V9c0-.021-.011-.04-.013-.062a.952.952 0 0 0-.051-.259c-.01-.032-.019-.063-.033-.093zM16.586 8H14V5.414L16.586 8zM6 20V4h6v5a1 1 0 0 0 1 1h5l.002 10H6z"/><path fill="currentColor" d="M8 12h8v2H8zm0 4h8v2H8zm0-8h2v2H8z"/></svg>
                </div>
                <div class="flex-grow-1 text-truncate fs-12" :title="c.filename">
                  {{ c.filename }}
                </div>
                <button class="btn btn-outline-secondary btn-sm ms-2" @click.stop="openViewer(c)">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="me-1">
                    <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5s5 2.24 5 5s-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3s3-1.34 3-3s-1.34-3-3-3z"/>
                  </svg>
                  View
                </button>
              </div>
            </div>
          </div>

          <div class="card-footer bg-white d-flex gap-2">
            <button class="btn btn-outline-secondary py-0 font-12 w-50" @click="openUpload(c)">Upload</button>
            <button class="btn btn-outline-secondary py-0 font-12 w-50 d-flex align-items-center justify-content-center" @click="openCommunication(c)">
              <span v-if="apiStore.hasCommentById(c._id)" class="dot me-1">•</span>
              <span>Add Comment</span>
            </button>
            <button class="btn btn-success btn-sm w-50" @click="onSend(c)">Send</button>
          </div>
        </div>
      </div>
    </div>


    <Editor
      v-if="isEditorVisible && selectedCourse"
      :term_code="selectedCourse.term_code"
      :id="selectedCourse._id"
      @close="isEditorVisible = false; selectedCourse = null; get_courses()"
    />
    <Upload
      v-if="isUploadVisible && selectedCourse"
      :term_code="selectedCourse.term_code"
      :college_code="selectedCourse.college_code"
      :trans_subj="selectedCourse.trans_subj"
      :trans_numb="selectedCourse.trans_numb"
      @uploaded="applyUpload"
      @close="isUploadVisible = false; selectedCourse = null"
    />

    <Viewer
      v-if="isViewerVisible && viewerFsid"
      :fsid="viewerFsid"
      :filename="viewerFilename"
      @close="isViewerVisible = false; viewerFsid = null; viewerFilename = ''"
    />

    <Communication
      v-if="isCommunicationVisible && application_id"
      :application_id="application_id"
      @close="isCommunicationVisible = false;"
      @new-comment="handleNewComment"
    />

  </div>
</template>

<script>
import { defineComponent } from 'vue'
import { useSessionStore } from '@/stores/SessionStore'
import { useTermStore } from '@/stores/TermStore'
import { useApiStore } from '@/stores/ApiStore'
import Upload from '@/components/documents/Upload.vue'
import Viewer from '@/components/documents/Viewer.vue'
import Editor from '@/components/Editor.vue'
import Communication from '@/components/Communication.vue'
import { useStorage } from '@vueuse/core'
import { StorageSerializers } from '@vueuse/core'

export default defineComponent({
  name: 'course-card',
  components: { Upload, Viewer, Communication, Editor },
  props: ['term_code', 'call_courses'],
  setup() {
    const sessionStore = useSessionStore()
    const termStore = useTermStore()
    const apiStore = useApiStore()
    return { sessionStore, termStore, apiStore }
  },
  data() {
    return {
      courses: [],
      search_filter: useStorage(`${process.env.VUE_APP_NAME}.search_filter`, '', localStorage, { serializer: StorageSerializers.object }),
      loading: false,
      isUploadVisible: false,
      selectedCourse: null,
      isEditorVisible: false,
      isViewerVisible: false,
      viewerFsid: null,
      viewerFilename: '',
      isCommunicationVisible: false,
      isManualVisible: false,
      application_id: null
    }
  },
  async mounted() {
    // await this.get_courses()
  },
  methods: {
    addManualCard() {
      this.isManualVisible = true
    },

    update_filter : _.debounce(function() {
      this.get_courses();
    }, 500),

    async get_courses() {
      this.loading = true;
      let filter_data = {
        search : this.search_filter
      }

      try {
        const resp = await this.sessionStore.request_data('POST', `/course?term_code=${encodeURIComponent(this.term_code)}`, 'get courses', filter_data)
        const payload = (resp && typeof resp === 'object' && 'data' in resp) ? resp.data : resp
        this.courses = Array.isArray(payload) ? payload : (payload ? Object.values(payload) : [])
      } finally {
        this.loading = false
      }
    },
    async openDetails(course) {
      if (course._details) {
        course._details = null
        return
      }
      try {
        const data = {
          trans_subj: course.trans_subj,
          id: course._id
        }
        const resp = await this.sessionStore.request_data(
          'POST',
          `/course/${encodeURIComponent(this.term_code)}/details`,
          'Fetching evaluator details...',
          data
        )
        const payload = (resp && typeof resp === 'object' && 'data' in resp) ? resp.data : resp
        course._details = payload
      } catch (e) {
        console.error(e)
      }
    },
    openEditor(course) {
      this.selectedCourse = course
      this.isEditorVisible = true
      console.log(course)
    },

    openUpload(course) {
      this.selectedCourse = course
      this.isUploadVisible = true
    },
    openViewer(course) {
      if (!course?.fsid) return
      this.viewerFsid = course.fsid
      this.viewerFilename = course.filename || ''
      this.isViewerVisible = true
    },
    openCommunication(course) {
      if (!course?._id) return;
      this.application_id = course._id;
      this.isCommunicationVisible = true;
      this.apiStore.clearNewComment(course._id);
    },
    applyUpload(p) {
      const match = this.courses.find(c =>
        c.term_code    === p.term_code &&
        c.college_code === p.college_code &&
        c.trans_subj   === p.trans_subj &&
        c.trans_numb   === p.trans_numb
      )
      if (match) {
        match.filename = p.filename
        match.fsid     = p.fsid
      }
    },
    async onSend(c) {
      let payload = {
        course_id: c._id,
        term_code: c.term_code,
        college_code: c.college_code,
        trans_subj: c.trans_subj,
        trans_numb: c.trans_numb
      }
      await this.sessionStore.request_data('PATCH', `****/send`, 'send course', payload)
      this.get_courses()
    },
    handleNewComment(courseId) {
      this.apiStore.markNewComment(courseId);
    }
  },
  computed: {
    orderedCourses() {
      return [...this.courses]
    }
  },
  watch: {
    search_filter : {
        handler(search, old_search) {
            if(search.length == 0 && old_search.length > 0)
                this.get_courses();
            else
                this.update_filter(); // calls search_requests via debounce - so it waits for sets of keystrokes
        }, deep: true
    },
    call_courses: {
      handler(newVal) {
        if (newVal) {
          this.get_courses()
          this.$emit('update:call_courses', false)
        }
      }
    },
    'term_code' : {
        async handler(term_code) {
            if(term_code){
                await this.update_filter()
            }
        },
        immediate: true
    }
  }
})
</script>

<style scoped>
.btn-outline-secondary {
  overflow: visible;
  position: relative;
}

.dot {
  color: inherit;
  font-size: 1.5em;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  animation: pulse 2s infinite;
  margin-top: -1px;
}

@keyframes pulse {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}
</style>
