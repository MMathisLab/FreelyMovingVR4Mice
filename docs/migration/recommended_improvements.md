# Recommended Improvements

After the DataJoint 2.0 migration is complete and stable, the following improvements can further enhance code quality, performance, and maintainability. These are organized by effort level and impact.

---

## Quick Wins

### Clean Up Schema Declarations

**Current state:** Schema declarations include explicit `locals()` and `create_tables=True` arguments:

```python
schema = dj.Schema("mice", locals(), create_tables=True)
```

**Recommendation:** Remove these arguments since they are the default behavior in DataJoint 2.0:

```python
schema = dj.Schema("mice")
```

**Effort:** Low

---

## Code Modernization

### Migrate fetch() Calls to New API

**Current state:** The codebase uses the legacy `fetch()` method with various arguments.

**Recommendation:** Update to the new DataJoint 2.0 query methods for clearer intent and better maintainability:

| Legacy Pattern | Recommended |
|----------------|-------------|
| `table.fetch()` | `table.to_dicts()` or `table.to_arrays()` |
| `table.fetch(as_dict=True)` | `table.to_dicts()` |
| `table.fetch(format="frame")` | `table.to_pandas()` |
| `table.fetch("KEY")` | `table.keys()` |

The new methods are more explicit about return types and align with DataJoint 2.0 conventions.

**Effort:** Medium

---

## High-Impact Improvements

### Built-in NumPy Array Codec

**Current state:** NumPy arrays are stored as generic `<blob>` fields with no type validation. Incorrect types are stored silently, which can cause downstream errors.

**Recommendation:** Create a custom `<numpy_array>` codec that validates data on insert. This catches type errors immediately and preserves dtype and shape metadata.

**Impact:** 90+ array fields across 12 tables (MouseState, State, Metadata, InterpolatedTrials, GuiParams, SignalsPhotodiode, and others).

**Effort:** Medium

---

### Custom DeepLabCut Codec

**Current state:** DeepLabCut DataFrames are manually decomposed into three separate fields (`data`, `headers`, `scorer`) using helper functions. Fetching requires reassembly via `dj_to_df()`.

**Recommendation:** Create a custom `<deeplabcut_keypoints>` codec that stores the complete DataFrame in a single field. This eliminates the need for `df_to_dj()` and `dj_to_df()` helper functions.

**Benefit:** Simpler code, reduced chance of mismatched data, and easier onboarding for new team members.

**Effort:** Medium

---

### Custom DataFrame Codec

**Current state:** General DataFrames are stored as generic blobs without index or dtype preservation guarantees.

**Recommendation:** Create a custom `<dataframe>` codec for native DataFrame serialization. This preserves index types, categorical dtypes, and column names automatically.

**Effort:** Low-Medium

---

## Performance Optimization

### Review Primary Key Structure

**Current state:** Some tables may have lengthy or compound primary keys.

**Recommendation:** Review primary key definitions across the schema to ensure keys are as concise as possible. Shorter primary keys significantly improve query performance, reduce storage overhead, and speed up join operations.

Tables with foreign key relationships benefit most from this optimization, as the key structure propagates through dependent tables.

**Effort:** Variable (requires schema analysis)

---

## File Management

### ObjectRef for File Paths

**Current state:** File paths are stored as `varchar` strings with no validation that files exist. Paths can silently break if files are moved or renamed.

**Recommendation:** Migrate file path fields to use DataJoint's `<filepath@store>` type. This provides:

- Validation that files exist on insert
- Automatic path management
- Streaming access for large files
- Future cloud storage support (S3, GCS)

**Fields affected:** `video_filepath`, `timestamp_filepath`, `keypoints_filepath`, `proc_filepath`, and experiment pickle file paths.

**Effort:** Medium-High

---

### External Storage for Large Arrays

**Current state:** Large arrays are stored directly in the database, which can bloat database size and slow backups.

**Recommendation:** Move large array fields to external hash-based storage. The database stores only a hash reference while the actual data lives in an external object store. This also provides automatic deduplication for identical arrays.

**Candidates:** `InterpolatedTrials` (25+ trajectory arrays per row), `GuiParams.cropped_image`, and any array fields exceeding 1MB.

**Effort:** Medium

---

## Future Considerations

### Cloud Storage Integration

Once ObjectRef migration is complete, the storage backend can be switched from local files to cloud storage (S3, GCS, Azure) with a configuration change. This enables:

- Scalable storage for large datasets
- Geographic distribution
- Cost optimization with storage tiers

**Effort:** Low (configuration only, after ObjectRef migration)

---

### Schema-Addressed Storage

For tables with very large data (neural recordings, video data), DataJoint 2.0 supports lazy-loading storage types (`<npy@>`, `<object@>`). Data is loaded on-demand rather than all at once, which is essential for datasets that exceed available memory.

**Effort:** Medium (for new tables or major refactoring)

---

## Summary

| Category | Recommendation | Effort | Impact |
|----------|----------------|--------|--------|
| Quick Wins | Clean up schema declarations | Low | Low |
| Code Modernization | Migrate fetch() to new API | Medium | Medium |
| High-Impact | NumPy array codec | Medium | High |
| High-Impact | DeepLabCut codec | Medium | High |
| High-Impact | DataFrame codec | Low-Medium | Medium |
| Performance | Review primary key structure | Variable | High |
| File Management | ObjectRef for file paths | Medium-High | Medium |
| File Management | External storage for large arrays | Medium | Medium |
| Future | Cloud storage integration | Low | Low |
| Future | Schema-addressed storage | Medium | Medium |

---

## Next Steps

We recommend implementing these improvements incrementally after the core migration is validated. The custom codecs provide the highest value for the effort involved and can be implemented one at a time. We can help with the design and implementation of any of these improvements.
