#define _GNU_SOURCE

#include <dlfcn.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef struct sqlite3 sqlite3;
typedef struct sqlite3_stmt sqlite3_stmt;

static pthread_mutex_t log_lock = PTHREAD_MUTEX_INITIALIZER;

static const char *hook_log_path(void) {
  const char *path = getenv("WECHAT_DB_HOOK_LOG");
  if (path && path[0]) {
    return path;
  }
  return "/tmp/wechat-db-hook.jsonl";
}

static long long now_ms(void) {
  struct timespec ts;
  clock_gettime(CLOCK_REALTIME, &ts);
  return ((long long)ts.tv_sec * 1000LL) + (ts.tv_nsec / 1000000LL);
}

static void hex_encode(const unsigned char *src, int n, char *dst, size_t dst_size) {
  static const char *digits = "0123456789abcdef";
  size_t needed = ((size_t)n * 2U) + 1U;
  if (!src || n <= 0 || dst_size < needed) {
    if (dst_size > 0) {
      dst[0] = '\0';
    }
    return;
  }
  for (int i = 0; i < n; ++i) {
    dst[i * 2] = digits[(src[i] >> 4) & 0xF];
    dst[i * 2 + 1] = digits[src[i] & 0xF];
  }
  dst[n * 2] = '\0';
}

static void json_escape(const char *src, char *dst, size_t dst_size) {
  if (!dst_size) {
    return;
  }
  size_t j = 0;
  for (size_t i = 0; src && src[i] && j + 2 < dst_size; ++i) {
    unsigned char c = (unsigned char)src[i];
    if (c == '\\' || c == '"') {
      dst[j++] = '\\';
      dst[j++] = (char)c;
    } else if (c == '\n') {
      dst[j++] = '\\';
      dst[j++] = 'n';
    } else if (c == '\r') {
      dst[j++] = '\\';
      dst[j++] = 'r';
    } else if (c >= 32 && c < 127) {
      dst[j++] = (char)c;
    }
  }
  dst[j] = '\0';
}

static void write_log(const char *event, const char *db_path, const char *sql, const char *key_hex) {
  FILE *fp;
  char escaped_path[2048];
  char escaped_sql[4096];
  pthread_mutex_lock(&log_lock);
  fp = fopen(hook_log_path(), "a");
  if (!fp) {
    pthread_mutex_unlock(&log_lock);
    return;
  }
  json_escape(db_path ? db_path : "", escaped_path, sizeof(escaped_path));
  json_escape(sql ? sql : "", escaped_sql, sizeof(escaped_sql));
  fprintf(
      fp,
      "{\"ts_ms\":%lld,\"event\":\"%s\",\"db_path\":\"%s\",\"sql\":\"%s\",\"key_hex\":\"%s\"}\n",
      now_ms(),
      event ? event : "",
      escaped_path,
      escaped_sql,
      key_hex ? key_hex : "");
  fclose(fp);
  pthread_mutex_unlock(&log_lock);
}

typedef const char *(*sqlite3_db_filename_fn)(sqlite3 *, const char *);

static const char *db_filename(sqlite3 *db, const char *db_name) {
  static sqlite3_db_filename_fn real_fn = NULL;
  if (!real_fn) {
    real_fn = (sqlite3_db_filename_fn)dlsym(RTLD_NEXT, "sqlite3_db_filename");
  }
  if (!real_fn || !db) {
    return "";
  }
  const char *path = real_fn(db, db_name ? db_name : "main");
  return path ? path : "";
}

int sqlite3_open_v2(const char *filename, sqlite3 **ppDb, int flags, const char *zVfs) {
  static int (*real_fn)(const char *, sqlite3 **, int, const char *) = NULL;
  if (!real_fn) {
    real_fn = dlsym(RTLD_NEXT, "sqlite3_open_v2");
  }
  int rc = real_fn(filename, ppDb, flags, zVfs);
  write_log("sqlite3_open_v2", filename ? filename : "", "", "");
  return rc;
}

int sqlite3_key(sqlite3 *db, const void *pKey, int nKey) {
  static int (*real_fn)(sqlite3 *, const void *, int) = NULL;
  char key_hex[4096];
  if (!real_fn) {
    real_fn = dlsym(RTLD_NEXT, "sqlite3_key");
  }
  hex_encode((const unsigned char *)pKey, nKey, key_hex, sizeof(key_hex));
  write_log("sqlite3_key", db_filename(db, "main"), "", key_hex);
  if (!real_fn) {
    return 1;
  }
  return real_fn(db, pKey, nKey);
}

int sqlite3_key_v2(sqlite3 *db, const char *zDbName, const void *pKey, int nKey) {
  static int (*real_fn)(sqlite3 *, const char *, const void *, int) = NULL;
  char key_hex[4096];
  if (!real_fn) {
    real_fn = dlsym(RTLD_NEXT, "sqlite3_key_v2");
  }
  hex_encode((const unsigned char *)pKey, nKey, key_hex, sizeof(key_hex));
  write_log("sqlite3_key_v2", db_filename(db, zDbName ? zDbName : "main"), "", key_hex);
  if (!real_fn) {
    return 1;
  }
  return real_fn(db, zDbName, pKey, nKey);
}

int sqlite3_exec(sqlite3 *db, const char *sql, int (*callback)(void *, int, char **, char **), void *arg, char **errmsg) {
  static int (*real_fn)(sqlite3 *, const char *, int (*)(void *, int, char **, char **), void *, char **) = NULL;
  if (!real_fn) {
    real_fn = dlsym(RTLD_NEXT, "sqlite3_exec");
  }
  if (sql && (strstr(sql, "PRAGMA") || strstr(sql, "pragma"))) {
    write_log("sqlite3_exec", db_filename(db, "main"), sql, "");
  }
  return real_fn(db, sql, callback, arg, errmsg);
}

int sqlite3_prepare_v2(sqlite3 *db, const char *zSql, int nByte, sqlite3_stmt **ppStmt, const char **pzTail) {
  static int (*real_fn)(sqlite3 *, const char *, int, sqlite3_stmt **, const char **) = NULL;
  if (!real_fn) {
    real_fn = dlsym(RTLD_NEXT, "sqlite3_prepare_v2");
  }
  if (zSql && (strstr(zSql, "PRAGMA") || strstr(zSql, "pragma"))) {
    write_log("sqlite3_prepare_v2", db_filename(db, "main"), zSql, "");
  }
  return real_fn(db, zSql, nByte, ppStmt, pzTail);
}
