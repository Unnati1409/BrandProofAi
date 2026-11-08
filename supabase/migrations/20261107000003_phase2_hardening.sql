-- ==============================================================================
-- Migration: 20261107000003_phase2_hardening.sql
-- BrandProof AI — Phase 2 Security, RLS & Relational Integrity Hardening
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Pre-Migration Data Validation Check
-- ------------------------------------------------------------------------------
DO $$
DECLARE
    mismatches INTEGER := 0;
BEGIN
    -- Check findings vs review_runs version mismatch
    SELECT COUNT(*) INTO mismatches
    FROM public.findings f
    JOIN public.review_runs rr ON f.run_id = rr.id
    WHERE f.content_version_id != rr.content_version_id OR f.workspace_id != rr.workspace_id;
    IF mismatches > 0 THEN
        RAISE EXCEPTION 'Pre-migration check failed: % findings have mismatched review_run or version', mismatches;
    END IF;

    -- Check content_approvals vs content_versions item mismatch
    SELECT COUNT(*) INTO mismatches
    FROM public.content_approvals ca
    JOIN public.content_versions cv ON ca.content_version_id = cv.id
    WHERE ca.content_id != cv.content_id OR ca.workspace_id != cv.workspace_id;
    IF mismatches > 0 THEN
        RAISE EXCEPTION 'Pre-migration check failed: % approvals have mismatched content_item', mismatches;
    END IF;

    -- Check rules vs catalogue_versions workspace mismatch
    SELECT COUNT(*) INTO mismatches
    FROM public.rules r
    JOIN public.catalogue_versions c ON r.catalogue_version_id = c.id
    WHERE r.workspace_id != c.workspace_id;
    IF mismatches > 0 THEN
        RAISE EXCEPTION 'Pre-migration check failed: % rules have mismatched catalogue workspace', mismatches;
    END IF;

    -- Check approved_facts vs catalogue_versions workspace mismatch
    SELECT COUNT(*) INTO mismatches
    FROM public.approved_facts f
    JOIN public.catalogue_versions c ON f.catalogue_version_id = c.id
    WHERE f.workspace_id != c.workspace_id;
    IF mismatches > 0 THEN
        RAISE EXCEPTION 'Pre-migration check failed: % facts have mismatched catalogue workspace', mismatches;
    END IF;

    RAISE NOTICE 'Pre-migration relational integrity verified: 0 mismatches found.';
END;
$$;

-- ------------------------------------------------------------------------------
-- 2. Least-Privilege Application Connection Role Provisioning
-- ------------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'brandproof_app') THEN
        CREATE ROLE brandproof_app WITH NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO brandproof_app;
GRANT authenticated TO brandproof_app;

-- ------------------------------------------------------------------------------
-- 3. Profiles Hardening: Drop password_hash & Add Auth Sync Trigger
-- ------------------------------------------------------------------------------
ALTER TABLE public.profiles DROP COLUMN IF EXISTS password_hash;

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
        NEW.raw_user_meta_data->>'avatar_url'
    )
    ON CONFLICT (id) DO UPDATE SET
        email = EXCLUDED.email,
        full_name = COALESCE(EXCLUDED.full_name, public.profiles.full_name),
        avatar_url = COALESCE(EXCLUDED.avatar_url, public.profiles.avatar_url),
        updated_at = now();
    RETURN NEW;
END;
$$;

ALTER FUNCTION public.handle_new_user() OWNER TO postgres;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR UPDATE ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ------------------------------------------------------------------------------
-- 4. Relational Integrity: Parent Unique Constraints & Same-Parent Foreign Keys
-- ------------------------------------------------------------------------------

-- Parent composite unique constraints
ALTER TABLE public.source_documents DROP CONSTRAINT IF EXISTS uq_source_documents_ws;
ALTER TABLE public.source_documents ADD CONSTRAINT uq_source_documents_ws UNIQUE (workspace_id, id);

ALTER TABLE public.source_passages DROP CONSTRAINT IF EXISTS uq_source_passages_ws;
ALTER TABLE public.source_passages ADD CONSTRAINT uq_source_passages_ws UNIQUE (workspace_id, id);

ALTER TABLE public.catalogue_versions DROP CONSTRAINT IF EXISTS uq_catalogue_versions_ws;
ALTER TABLE public.catalogue_versions ADD CONSTRAINT uq_catalogue_versions_ws UNIQUE (workspace_id, id);

ALTER TABLE public.rules DROP CONSTRAINT IF EXISTS uq_rules_ws;
ALTER TABLE public.rules ADD CONSTRAINT uq_rules_ws UNIQUE (workspace_id, id);

ALTER TABLE public.approved_facts DROP CONSTRAINT IF EXISTS uq_approved_facts_ws;
ALTER TABLE public.approved_facts ADD CONSTRAINT uq_approved_facts_ws UNIQUE (workspace_id, id);

ALTER TABLE public.assets DROP CONSTRAINT IF EXISTS uq_assets_ws;
ALTER TABLE public.assets ADD CONSTRAINT uq_assets_ws UNIQUE (workspace_id, id);

ALTER TABLE public.content_items DROP CONSTRAINT IF EXISTS uq_content_items_ws;
ALTER TABLE public.content_items ADD CONSTRAINT uq_content_items_ws UNIQUE (workspace_id, id);

ALTER TABLE public.content_versions DROP CONSTRAINT IF EXISTS uq_content_versions_ws;
ALTER TABLE public.content_versions ADD CONSTRAINT uq_content_versions_ws UNIQUE (workspace_id, id);

ALTER TABLE public.content_versions DROP CONSTRAINT IF EXISTS uq_content_versions_item_ws;
ALTER TABLE public.content_versions ADD CONSTRAINT uq_content_versions_item_ws UNIQUE (workspace_id, content_id, id);

ALTER TABLE public.review_runs DROP CONSTRAINT IF EXISTS uq_review_runs_ver_ws;
ALTER TABLE public.review_runs ADD CONSTRAINT uq_review_runs_ver_ws UNIQUE (workspace_id, content_version_id, id);

ALTER TABLE public.findings DROP CONSTRAINT IF EXISTS uq_findings_ver_ws;
ALTER TABLE public.findings ADD CONSTRAINT uq_findings_ver_ws UNIQUE (workspace_id, content_version_id, id);

-- Same-Parent Composite Foreign Keys
ALTER TABLE public.source_passages DROP CONSTRAINT IF EXISTS fk_source_passages_document_ws;
ALTER TABLE public.source_passages
    ADD CONSTRAINT fk_source_passages_document_ws
    FOREIGN KEY (workspace_id, document_id)
    REFERENCES public.source_documents (workspace_id, id)
    ON DELETE CASCADE;

ALTER TABLE public.rules DROP CONSTRAINT IF EXISTS fk_rules_catalogue_ws;
ALTER TABLE public.rules
    ADD CONSTRAINT fk_rules_catalogue_ws
    FOREIGN KEY (workspace_id, catalogue_version_id)
    REFERENCES public.catalogue_versions (workspace_id, id)
    ON DELETE SET NULL;

ALTER TABLE public.rules DROP CONSTRAINT IF EXISTS fk_rules_passage_ws;
ALTER TABLE public.rules
    ADD CONSTRAINT fk_rules_passage_ws
    FOREIGN KEY (workspace_id, source_passage_id)
    REFERENCES public.source_passages (workspace_id, id)
    ON DELETE SET NULL;

ALTER TABLE public.approved_facts DROP CONSTRAINT IF EXISTS fk_facts_catalogue_ws;
ALTER TABLE public.approved_facts
    ADD CONSTRAINT fk_facts_catalogue_ws
    FOREIGN KEY (workspace_id, catalogue_version_id)
    REFERENCES public.catalogue_versions (workspace_id, id)
    ON DELETE SET NULL;

ALTER TABLE public.approved_facts DROP CONSTRAINT IF EXISTS fk_facts_passage_ws;
ALTER TABLE public.approved_facts
    ADD CONSTRAINT fk_facts_passage_ws
    FOREIGN KEY (workspace_id, source_passage_id)
    REFERENCES public.source_passages (workspace_id, id)
    ON DELETE SET NULL;

ALTER TABLE public.content_versions DROP CONSTRAINT IF EXISTS fk_content_versions_item_ws;
ALTER TABLE public.content_versions
    ADD CONSTRAINT fk_content_versions_item_ws
    FOREIGN KEY (workspace_id, content_id)
    REFERENCES public.content_items (workspace_id, id)
    ON DELETE CASCADE;

ALTER TABLE public.review_runs DROP CONSTRAINT IF EXISTS fk_review_runs_version_ws;
ALTER TABLE public.review_runs
    ADD CONSTRAINT fk_review_runs_version_ws
    FOREIGN KEY (workspace_id, content_version_id)
    REFERENCES public.content_versions (workspace_id, id)
    ON DELETE CASCADE;

ALTER TABLE public.review_runs DROP CONSTRAINT IF EXISTS fk_review_runs_catalogue_ws;
ALTER TABLE public.review_runs
    ADD CONSTRAINT fk_review_runs_catalogue_ws
    FOREIGN KEY (workspace_id, catalogue_version_id)
    REFERENCES public.catalogue_versions (workspace_id, id)
    ON DELETE SET NULL;

ALTER TABLE public.findings DROP CONSTRAINT IF EXISTS fk_findings_run_ver_ws;
ALTER TABLE public.findings
    ADD CONSTRAINT fk_findings_run_ver_ws
    FOREIGN KEY (workspace_id, content_version_id, run_id)
    REFERENCES public.review_runs (workspace_id, content_version_id, id)
    ON DELETE CASCADE;

ALTER TABLE public.findings DROP CONSTRAINT IF EXISTS fk_findings_rule_ws;
ALTER TABLE public.findings
    ADD CONSTRAINT fk_findings_rule_ws
    FOREIGN KEY (workspace_id, rule_id)
    REFERENCES public.rules (workspace_id, id)
    ON DELETE SET NULL;

ALTER TABLE public.findings DROP CONSTRAINT IF EXISTS fk_findings_fact_ws;
ALTER TABLE public.findings
    ADD CONSTRAINT fk_findings_fact_ws
    FOREIGN KEY (workspace_id, fact_id)
    REFERENCES public.approved_facts (workspace_id, id)
    ON DELETE SET NULL;

ALTER TABLE public.content_comments DROP CONSTRAINT IF EXISTS fk_comments_version_ws;
ALTER TABLE public.content_comments
    ADD CONSTRAINT fk_comments_version_ws
    FOREIGN KEY (workspace_id, content_version_id)
    REFERENCES public.content_versions (workspace_id, id)
    ON DELETE CASCADE;

ALTER TABLE public.content_comments DROP CONSTRAINT IF EXISTS fk_comments_finding_ver_ws;
ALTER TABLE public.content_comments
    ADD CONSTRAINT fk_comments_finding_ver_ws
    FOREIGN KEY (workspace_id, content_version_id, finding_id)
    REFERENCES public.findings (workspace_id, content_version_id, id)
    ON DELETE CASCADE;

ALTER TABLE public.content_approvals DROP CONSTRAINT IF EXISTS fk_approvals_item_ver_ws;
ALTER TABLE public.content_approvals
    ADD CONSTRAINT fk_approvals_item_ver_ws
    FOREIGN KEY (workspace_id, content_id, content_version_id)
    REFERENCES public.content_versions (workspace_id, content_id, id)
    ON DELETE CASCADE;

-- ------------------------------------------------------------------------------
-- 5. Drop Legacy Policies & Helpers, then Recreate Non-Recursive RLS Helpers
-- ------------------------------------------------------------------------------

-- Drop existing baseline policies first so dependent functions can be safely replaced
DO $$
DECLARE
    pol RECORD;
BEGIN
    FOR pol IN
        SELECT schemaname, tablename, policyname
        FROM pg_policies
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I.%I', pol.policyname, pol.schemaname, pol.tablename);
    END LOOP;
END $$;

DROP FUNCTION IF EXISTS public.is_workspace_member(UUID) CASCADE;
DROP FUNCTION IF EXISTS public.has_workspace_role(UUID, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.get_user_workspace_ids(TEXT) CASCADE;

CREATE OR REPLACE FUNCTION public.get_user_workspace_ids(p_role TEXT DEFAULT NULL)
RETURNS SETOF UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT workspace_id
    FROM public.workspace_members
    WHERE user_id = auth.uid()
      AND (p_role IS NULL OR p_role = ANY(roles));
$$;

ALTER FUNCTION public.get_user_workspace_ids(TEXT) OWNER TO postgres;

CREATE OR REPLACE FUNCTION public.is_workspace_member(p_workspace_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.workspace_members
        WHERE workspace_id = p_workspace_id
          AND user_id = auth.uid()
    );
$$;

ALTER FUNCTION public.is_workspace_member(UUID) OWNER TO postgres;

CREATE OR REPLACE FUNCTION public.has_workspace_role(p_workspace_id UUID, p_role TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.workspace_members
        WHERE workspace_id = p_workspace_id
          AND user_id = auth.uid()
          AND p_role = ANY(roles)
    );
$$;

ALTER FUNCTION public.has_workspace_role(UUID, TEXT) OWNER TO postgres;

-- ------------------------------------------------------------------------------
-- 6. Apply Complete 17-Table Authorization Specification
-- ------------------------------------------------------------------------------

-- 1. profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles FORCE ROW LEVEL SECURITY;

CREATE POLICY profiles_select_policy ON public.profiles
    FOR SELECT TO authenticated
    USING (
        id = auth.uid()
        OR id IN (
            SELECT wm.user_id
            FROM public.workspace_members wm
            WHERE wm.workspace_id IN (SELECT public.get_user_workspace_ids())
        )
    );

CREATE POLICY profiles_update_policy ON public.profiles
    FOR UPDATE TO authenticated
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- 2. workspaces
ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspaces FORCE ROW LEVEL SECURITY;

CREATE POLICY workspaces_select_policy ON public.workspaces
    FOR SELECT TO authenticated
    USING (
        created_by = auth.uid()
        OR id IN (SELECT public.get_user_workspace_ids())
    );

CREATE POLICY workspaces_insert_policy ON public.workspaces
    FOR INSERT TO authenticated
    WITH CHECK (created_by = auth.uid());

CREATE POLICY workspaces_update_policy ON public.workspaces
    FOR UPDATE TO authenticated
    USING (id IN (SELECT public.get_user_workspace_ids('admin')))
    WITH CHECK (id IN (SELECT public.get_user_workspace_ids('admin')));

CREATE POLICY workspaces_delete_policy ON public.workspaces
    FOR DELETE TO authenticated
    USING (id IN (SELECT public.get_user_workspace_ids('admin')));

-- 3. workspace_members (ENABLE RLS without FORCE to prevent recursion during SECURITY DEFINER helper lookups)
ALTER TABLE public.workspace_members ENABLE ROW LEVEL SECURITY;

CREATE POLICY members_select_policy ON public.workspace_members
    FOR SELECT TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        OR user_id = auth.uid()
    );

CREATE POLICY members_insert_policy ON public.workspace_members
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids('admin'))
        OR (
            user_id = auth.uid()
            AND workspace_id IN (SELECT id FROM public.workspaces WHERE created_by = auth.uid())
        )
    );

CREATE POLICY members_update_policy ON public.workspace_members
    FOR UPDATE TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids('admin')))
    WITH CHECK (workspace_id IN (SELECT public.get_user_workspace_ids('admin')));

CREATE POLICY members_delete_policy ON public.workspace_members
    FOR DELETE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids('admin'))
        OR user_id = auth.uid()
    );

-- 4. source_documents
ALTER TABLE public.source_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_documents FORCE ROW LEVEL SECURITY;

CREATE POLICY source_documents_select_policy ON public.source_documents
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY source_documents_insert_policy ON public.source_documents
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
        )
        AND uploaded_by = auth.uid()
    );

CREATE POLICY source_documents_update_policy ON public.source_documents
    FOR UPDATE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
        )
    );

CREATE POLICY source_documents_delete_policy ON public.source_documents
    FOR DELETE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
        )
    );

-- 5. source_passages
ALTER TABLE public.source_passages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_passages FORCE ROW LEVEL SECURITY;

CREATE POLICY source_passages_select_policy ON public.source_passages
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY source_passages_insert_policy ON public.source_passages
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
        )
    );

CREATE POLICY source_passages_update_policy ON public.source_passages
    FOR UPDATE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
        )
    );

CREATE POLICY source_passages_delete_policy ON public.source_passages
    FOR DELETE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
        )
    );

-- 6. catalogue_versions
ALTER TABLE public.catalogue_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.catalogue_versions FORCE ROW LEVEL SECURITY;

CREATE POLICY catalogue_versions_select_policy ON public.catalogue_versions
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY catalogue_versions_insert_policy ON public.catalogue_versions
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
        )
        AND created_by = auth.uid()
    );

CREATE POLICY catalogue_versions_update_policy ON public.catalogue_versions
    FOR UPDATE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
        )
    );

-- 7. rules
ALTER TABLE public.rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rules FORCE ROW LEVEL SECURITY;

CREATE POLICY rules_select_policy ON public.rules
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY rules_insert_policy ON public.rules
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
        )
    );

CREATE POLICY rules_update_policy ON public.rules
    FOR UPDATE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
        )
    );

CREATE POLICY rules_delete_policy ON public.rules
    FOR DELETE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
        )
    );

-- 8. approved_facts
ALTER TABLE public.approved_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approved_facts FORCE ROW LEVEL SECURITY;

CREATE POLICY facts_select_policy ON public.approved_facts
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY facts_insert_policy ON public.approved_facts
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
        )
    );

CREATE POLICY facts_update_policy ON public.approved_facts
    FOR UPDATE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
        )
    );

CREATE POLICY facts_delete_policy ON public.approved_facts
    FOR DELETE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
        )
    );

-- 9. tone_attributes
ALTER TABLE public.tone_attributes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tone_attributes FORCE ROW LEVEL SECURITY;

CREATE POLICY tone_attributes_select_policy ON public.tone_attributes
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY tone_attributes_insert_policy ON public.tone_attributes
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
        )
    );

CREATE POLICY tone_attributes_update_policy ON public.tone_attributes
    FOR UPDATE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
        )
    );

CREATE POLICY tone_attributes_delete_policy ON public.tone_attributes
    FOR DELETE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
        )
    );

-- 10. assets
ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assets FORCE ROW LEVEL SECURITY;

CREATE POLICY assets_select_policy ON public.assets
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY assets_insert_policy ON public.assets
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
            OR public.has_workspace_role(workspace_id, 'creator')
        )
        AND created_by = auth.uid()
    );

CREATE POLICY assets_update_policy ON public.assets
    FOR UPDATE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR created_by = auth.uid()
        )
    );

CREATE POLICY assets_delete_policy ON public.assets
    FOR DELETE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
        )
    );

-- 11. content_items
ALTER TABLE public.content_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_items FORCE ROW LEVEL SECURITY;

CREATE POLICY content_items_select_policy ON public.content_items
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY content_items_insert_policy ON public.content_items
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND created_by = auth.uid()
    );

CREATE POLICY content_items_update_policy ON public.content_items
    FOR UPDATE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            created_by = auth.uid()
            OR public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'manager')
            OR public.has_workspace_role(workspace_id, 'reviewer')
        )
    );

CREATE POLICY content_items_delete_policy ON public.content_items
    FOR DELETE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            created_by = auth.uid()
            OR public.has_workspace_role(workspace_id, 'admin')
        )
    );

-- 12. content_versions
ALTER TABLE public.content_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_versions FORCE ROW LEVEL SECURITY;

CREATE POLICY content_versions_select_policy ON public.content_versions
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY content_versions_insert_policy ON public.content_versions
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND created_by = auth.uid()
    );

-- 13. review_runs
ALTER TABLE public.review_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_runs FORCE ROW LEVEL SECURITY;

CREATE POLICY review_runs_select_policy ON public.review_runs
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY review_runs_insert_policy ON public.review_runs
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND created_by = auth.uid()
    );

CREATE POLICY review_runs_update_policy ON public.review_runs
    FOR UPDATE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            created_by = auth.uid()
            OR public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'manager')
            OR public.has_workspace_role(workspace_id, 'reviewer')
        )
    );

-- 14. findings (SELECT granted; INSERT/UPDATE strictly mediated via record_review_finding)
ALTER TABLE public.findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.findings FORCE ROW LEVEL SECURITY;

CREATE POLICY findings_select_policy ON public.findings
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

-- 15. content_comments
ALTER TABLE public.content_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_comments FORCE ROW LEVEL SECURITY;

CREATE POLICY content_comments_select_policy ON public.content_comments
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY content_comments_insert_policy ON public.content_comments
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND author_id = auth.uid()
    );

CREATE POLICY content_comments_update_policy ON public.content_comments
    FOR UPDATE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            author_id = auth.uid()
            OR public.has_workspace_role(workspace_id, 'admin')
        )
    );

CREATE POLICY content_comments_delete_policy ON public.content_comments
    FOR DELETE TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            author_id = auth.uid()
            OR public.has_workspace_role(workspace_id, 'admin')
        )
    );

-- 16. content_approvals
ALTER TABLE public.content_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_approvals FORCE ROW LEVEL SECURITY;

CREATE POLICY content_approvals_select_policy ON public.content_approvals
    FOR SELECT TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

CREATE POLICY content_approvals_insert_policy ON public.content_approvals
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
            OR public.has_workspace_role(workspace_id, 'reviewer')
        )
        AND decided_by = auth.uid()
    );

-- 17. audit_logs (SELECT granted to admins/managers; INSERT strictly mediated via record_audit_event)
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs FORCE ROW LEVEL SECURITY;

CREATE POLICY audit_logs_select_policy ON public.audit_logs
    FOR SELECT TO authenticated
    USING (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'admin')
            OR public.has_workspace_role(workspace_id, 'brand_owner')
            OR public.has_workspace_role(workspace_id, 'manager')
        )
    );

-- ------------------------------------------------------------------------------
-- 7. Critical Workflow State Protection Triggers
-- ------------------------------------------------------------------------------

-- Trigger 1: Protect content item workflow state & creator immutability
CREATE OR REPLACE FUNCTION public.protect_content_item_state()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    -- 1. Immutable fields
    IF NEW.created_by IS DISTINCT FROM OLD.created_by THEN
        RAISE EXCEPTION 'Security violation: created_by is immutable on content_items'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.workspace_id IS DISTINCT FROM OLD.workspace_id THEN
        RAISE EXCEPTION 'Security violation: workspace_id is immutable on content_items'
            USING ERRCODE = 'check_violation';
    END IF;

    -- 2. State transition protection: cannot mutate state directly to 'approved' without valid approval record
    IF NEW.state = 'approved' AND OLD.state IS DISTINCT FROM 'approved' THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.content_approvals ca
            WHERE ca.content_id = NEW.id
              AND ca.decision = 'approved'
        ) THEN
            RAISE EXCEPTION 'Workflow violation: content item cannot transition to approved state without a formal approval record'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

ALTER FUNCTION public.protect_content_item_state() OWNER TO postgres;

DROP TRIGGER IF EXISTS trg_protect_content_item_state ON public.content_items;
CREATE TRIGGER trg_protect_content_item_state
    BEFORE UPDATE ON public.content_items
    FOR EACH ROW
    EXECUTE FUNCTION public.protect_content_item_state();

-- Trigger 2: Creator separation & approver validation on content_approvals
CREATE OR REPLACE FUNCTION public.check_creator_not_approver()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    content_creator UUID;
    caller_uid UUID;
BEGIN
    caller_uid := auth.uid();

    -- Actor validation: caller cannot forge decided_by or omit identity
    IF caller_uid IS NULL OR NEW.decided_by IS DISTINCT FROM caller_uid THEN
        RAISE EXCEPTION 'Security violation: decided_by must match authenticated caller identity'
            USING ERRCODE = 'check_violation';
    END IF;

    -- Retrieve content creator
    SELECT created_by INTO content_creator
    FROM public.content_items
    WHERE id = NEW.content_id;

    IF content_creator IS NULL THEN
        RAISE EXCEPTION 'Invalid reference: content item does not exist'
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    -- Self-approval prohibition
    IF content_creator = caller_uid THEN
        RAISE EXCEPTION 'Governance rule violation: Content creator cannot approve their own content submission'
            USING ERRCODE = 'check_violation';
    END IF;

    -- When approved, update the content item state to approved
    IF NEW.decision = 'approved' THEN
        UPDATE public.content_items
        SET state = 'approved', updated_at = now()
        WHERE id = NEW.content_id;
    END IF;

    RETURN NEW;
END;
$$;

ALTER FUNCTION public.check_creator_not_approver() OWNER TO postgres;

DROP TRIGGER IF EXISTS trg_creator_cannot_approve ON public.content_approvals;
DROP TRIGGER IF EXISTS trg_check_creator_not_approver ON public.content_approvals;
CREATE TRIGGER trg_check_creator_not_approver
    AFTER INSERT ON public.content_approvals
    FOR EACH ROW
    EXECUTE FUNCTION public.check_creator_not_approver();

-- Trigger 3: Hardened Sole-Admin Protection (Relational AFTER Trigger with Row Lock)
CREATE OR REPLACE FUNCTION public.prevent_orphan_workspace()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    target_ws_id UUID;
    remaining_admins INTEGER;
BEGIN
    target_ws_id := COALESCE(OLD.workspace_id, NEW.workspace_id);

    -- 1. If the parent workspace does not exist in this transaction, it was deleted (or is being deleted).
    -- Cascade deletion of members is permitted.
    IF NOT EXISTS (SELECT 1 FROM public.workspaces WHERE id = target_ws_id) THEN
        RETURN NULL;
    END IF;

    -- 2. Check if the operation removes, demotes, or transfers an Admin
    IF (TG_OP = 'DELETE' AND ('admin' = ANY(OLD.roles))) OR
       (TG_OP = 'UPDATE' AND ('admin' = ANY(OLD.roles)) AND NOT ('admin' = ANY(NEW.roles))) OR
       (TG_OP = 'UPDATE' AND ('admin' = ANY(OLD.roles)) AND NEW.workspace_id IS DISTINCT FROM OLD.workspace_id) THEN

        -- Acquire exclusive lock on the parent workspace row to serialize concurrent transactions
        PERFORM 1 FROM public.workspaces WHERE id = target_ws_id FOR UPDATE;

        -- Re-verify parent existence after acquiring lock
        IF NOT EXISTS (SELECT 1 FROM public.workspaces WHERE id = target_ws_id) THEN
            RETURN NULL;
        END IF;

        -- Count remaining active admins for this workspace
        SELECT COUNT(*) INTO remaining_admins
        FROM public.workspace_members
        WHERE workspace_id = target_ws_id
          AND 'admin' = ANY(roles);

        IF remaining_admins = 0 THEN
            RAISE EXCEPTION 'Cannot remove or demote the sole Administrator of workspace %', target_ws_id
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    RETURN NULL;
END;
$$;

ALTER FUNCTION public.prevent_orphan_workspace() OWNER TO postgres;

DROP TRIGGER IF EXISTS trg_prevent_orphan_workspace ON public.workspace_members;
CREATE TRIGGER trg_prevent_orphan_workspace
    AFTER DELETE OR UPDATE OF roles, workspace_id
    ON public.workspace_members
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_orphan_workspace();

-- ------------------------------------------------------------------------------
-- 8. Atomic Workspace Procedures
-- ------------------------------------------------------------------------------

-- Atomic Workspace Creation Procedure
CREATE OR REPLACE FUNCTION public.create_workspace(
    p_name TEXT,
    p_slug TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    new_ws_id UUID;
    caller_uid UUID;
BEGIN
    caller_uid := auth.uid();
    IF caller_uid IS NULL THEN
        RAISE EXCEPTION 'Unauthenticated caller cannot create a workspace' USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF length(trim(p_name)) < 2 OR length(trim(p_name)) > 100 THEN
        RAISE EXCEPTION 'Invalid workspace name length' USING ERRCODE = 'check_violation';
    END IF;

    IF length(trim(p_slug)) < 2 OR length(trim(p_slug)) > 50 THEN
        RAISE EXCEPTION 'Invalid workspace slug length' USING ERRCODE = 'check_violation';
    END IF;

    -- 1. Insert workspace
    INSERT INTO public.workspaces (name, slug, created_by)
    VALUES (trim(p_name), lower(trim(p_slug)), caller_uid)
    RETURNING id INTO new_ws_id;

    -- 2. Insert creator as Admin member
    INSERT INTO public.workspace_members (workspace_id, user_id, roles)
    VALUES (new_ws_id, caller_uid, ARRAY['admin']::TEXT[]);

    -- 3. Record audit event
    INSERT INTO public.audit_logs (workspace_id, actor_id, event_type, target_type, target_id, details)
    VALUES (new_ws_id, caller_uid, 'workspace.created', 'workspace', new_ws_id::text, jsonb_build_object('name', p_name, 'slug', p_slug));

    RETURN new_ws_id;
END;
$$;

ALTER FUNCTION public.create_workspace(TEXT, TEXT) OWNER TO postgres;
REVOKE ALL ON FUNCTION public.create_workspace(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.create_workspace(TEXT, TEXT) TO authenticated;

-- Controlled Workspace Deletion Procedure
CREATE OR REPLACE FUNCTION public.delete_workspace(p_workspace_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    IF auth.uid() IS NULL OR NOT public.has_workspace_role(p_workspace_id, 'admin') THEN
        RAISE EXCEPTION 'Permission denied: Caller must be an Administrator of workspace % to delete it', p_workspace_id
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    -- Delete workspace (cascades automatically to members, documents, content, and audit logs)
    DELETE FROM public.workspaces WHERE id = p_workspace_id;
END;
$$;

ALTER FUNCTION public.delete_workspace(UUID) OWNER TO postgres;
REVOKE ALL ON FUNCTION public.delete_workspace(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.delete_workspace(UUID) TO authenticated;

-- ------------------------------------------------------------------------------
-- 9. Privileged Write Stored Procedures: Review Findings & Audit Logging
-- ------------------------------------------------------------------------------

-- Trusted Review Finding Recording Procedure
CREATE OR REPLACE FUNCTION public.record_review_finding(
    p_workspace_id UUID,
    p_run_id UUID,
    p_content_version_id UUID,
    p_category TEXT,
    p_severity TEXT,
    p_basis_label TEXT,
    p_start_offset INTEGER,
    p_end_offset INTEGER,
    p_quoted_submitted_content TEXT,
    p_quoted_approved_source TEXT,
    p_source_reference TEXT,
    p_explanation TEXT,
    p_rule_id UUID DEFAULT NULL,
    p_fact_id UUID DEFAULT NULL,
    p_verdict TEXT DEFAULT NULL,
    p_confidence_indicator TEXT DEFAULT NULL,
    p_suggestions JSONB DEFAULT '[]'::jsonb,
    p_paragraph_index INTEGER DEFAULT NULL,
    p_page_number INTEGER DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    new_finding_id UUID;
    caller_uid UUID;
    run_status TEXT;
    run_creator UUID;
BEGIN
    caller_uid := auth.uid();

    -- 1. Authentication & Active Workspace Membership
    IF caller_uid IS NULL OR NOT public.is_workspace_member(p_workspace_id) THEN
        RAISE EXCEPTION 'Finding creation rejected: Caller is not an active member of workspace %', p_workspace_id
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    -- 2. Validate composite relational integrity and retrieve review run status
    SELECT rr.status, rr.created_by INTO run_status, run_creator
    FROM public.review_runs rr
    WHERE rr.id = p_run_id
      AND rr.workspace_id = p_workspace_id
      AND rr.content_version_id = p_content_version_id;

    IF run_status IS NULL THEN
        RAISE EXCEPTION 'Relational mismatch: review_run % does not match workspace % or content_version %',
            p_run_id, p_workspace_id, p_content_version_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    -- 3. Authorization Check: Caller must be an admin, manager, reviewer, or the creator of the run
    IF NOT (
        public.has_workspace_role(p_workspace_id, 'admin')
        OR public.has_workspace_role(p_workspace_id, 'manager')
        OR public.has_workspace_role(p_workspace_id, 'reviewer')
        OR run_creator = caller_uid
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Caller cannot record findings for review_run %', p_run_id
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    -- 4. Run State Validation: Findings can only be recorded while run is active (running or queued)
    IF run_status NOT IN ('running', 'queued') THEN
        RAISE EXCEPTION 'Review run % is in state % and cannot accept new findings', p_run_id, run_status
            USING ERRCODE = 'check_violation';
    END IF;

    -- 5. Evidence & Parameter Validation
    IF p_start_offset < 0 OR p_end_offset < p_start_offset THEN
        RAISE EXCEPTION 'Invalid finding text offsets: start=% end=%', p_start_offset, p_end_offset
            USING ERRCODE = 'check_violation';
    END IF;

    IF length(trim(coalesce(p_explanation, ''))) < 5 THEN
        RAISE EXCEPTION 'Finding explanation must be at least 5 characters'
            USING ERRCODE = 'check_violation';
    END IF;

    -- 6. Validate optional rule_id belongs to the SAME workspace
    IF p_rule_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.rules r WHERE r.id = p_rule_id AND r.workspace_id = p_workspace_id
    ) THEN
        RAISE EXCEPTION 'Cross-workspace reference rejected: rule % does not belong to workspace %',
            p_rule_id, p_workspace_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    -- 7. Validate optional fact_id belongs to the SAME workspace
    IF p_fact_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.approved_facts f WHERE f.id = p_fact_id AND f.workspace_id = p_workspace_id
    ) THEN
        RAISE EXCEPTION 'Cross-workspace reference rejected: fact % does not belong to workspace %',
            p_fact_id, p_workspace_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    -- 8. Insert finding
    INSERT INTO public.findings (
        workspace_id, run_id, content_version_id, category, severity, basis_label,
        start_offset, end_offset, quoted_submitted_content, quoted_approved_source,
        source_reference, explanation, rule_id, fact_id, verdict,
        confidence_indicator, suggestions, paragraph_index, page_number
    ) VALUES (
        p_workspace_id, p_run_id, p_content_version_id, p_category, p_severity, p_basis_label,
        p_start_offset, p_end_offset, p_quoted_submitted_content, p_quoted_approved_source,
        p_source_reference, p_explanation, p_rule_id, p_fact_id, p_verdict,
        p_confidence_indicator, p_suggestions, p_paragraph_index, p_page_number
    ) RETURNING id INTO new_finding_id;

    RETURN new_finding_id;
END;
$$;

ALTER FUNCTION public.record_review_finding(UUID, UUID, UUID, TEXT, TEXT, TEXT, INTEGER, INTEGER, TEXT, TEXT, TEXT, TEXT, UUID, UUID, TEXT, TEXT, JSONB, INTEGER, INTEGER) OWNER TO postgres;
REVOKE ALL ON FUNCTION public.record_review_finding(UUID, UUID, UUID, TEXT, TEXT, TEXT, INTEGER, INTEGER, TEXT, TEXT, TEXT, TEXT, UUID, UUID, TEXT, TEXT, JSONB, INTEGER, INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.record_review_finding(UUID, UUID, UUID, TEXT, TEXT, TEXT, INTEGER, INTEGER, TEXT, TEXT, TEXT, TEXT, UUID, UUID, TEXT, TEXT, JSONB, INTEGER, INTEGER) TO authenticated;

-- Trusted Audit Event Recording Procedure
CREATE OR REPLACE FUNCTION public.record_audit_event(
    p_workspace_id UUID,
    p_event_type TEXT,
    p_target_type TEXT,
    p_target_id TEXT,
    p_details JSONB DEFAULT '{}'::jsonb,
    p_ip_address TEXT DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    caller_uid UUID;
    new_audit_id BIGINT;
    clean_event TEXT;
BEGIN
    caller_uid := auth.uid();

    -- 1. Identity & Membership: Must be authenticated and confirmed workspace member
    IF caller_uid IS NULL OR NOT public.is_workspace_member(p_workspace_id) THEN
        RAISE EXCEPTION 'Audit logging rejected: Caller is not authenticated or not a workspace member'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    clean_event := lower(trim(p_event_type));

    -- 2. Input Sanitation
    IF length(clean_event) < 3 OR length(clean_event) > 100 THEN
        RAISE EXCEPTION 'Invalid audit event_type length' USING ERRCODE = 'check_violation';
    END IF;

    -- 3. Event Authorization Check:
    -- Administrative events require 'admin' role
    IF clean_event IN ('workspace.updated', 'workspace.deleted', 'member.invited', 'member.role_changed', 'member.removed', 'api_key.rotated', 'settings.updated') THEN
        IF NOT public.has_workspace_role(p_workspace_id, 'admin') THEN
            RAISE EXCEPTION 'Unauthorized: Caller lacks administrative privileges to log event %', clean_event
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    -- Editorial / catalogue events require admin, brand_owner, or manager
    ELSIF clean_event IN ('catalogue.published', 'rule.created', 'rule.updated', 'rule.deleted', 'fact.created', 'fact.updated', 'fact.deleted') THEN
        IF NOT (
            public.has_workspace_role(p_workspace_id, 'admin')
            OR public.has_workspace_role(p_workspace_id, 'brand_owner')
            OR public.has_workspace_role(p_workspace_id, 'manager')
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Caller lacks editorial privileges to log event %', clean_event
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;

    -- 4. Insert into audit_logs (actor_id derived strictly from auth.uid(), never from caller parameter)
    INSERT INTO public.audit_logs (
        workspace_id, actor_id, event_type, target_type, target_id, details, ip_address
    ) VALUES (
        p_workspace_id, caller_uid, clean_event, trim(p_target_type), trim(p_target_id), p_details, p_ip_address
    ) RETURNING id INTO new_audit_id;

    RETURN new_audit_id;
END;
$$;

ALTER FUNCTION public.record_audit_event(UUID, TEXT, TEXT, TEXT, JSONB, TEXT) OWNER TO postgres;
REVOKE ALL ON FUNCTION public.record_audit_event(UUID, TEXT, TEXT, TEXT, JSONB, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.record_audit_event(UUID, TEXT, TEXT, TEXT, JSONB, TEXT) TO authenticated;

-- Helper: lookup or create profile for workspace invitations
CREATE OR REPLACE FUNCTION public.lookup_or_create_profile(p_email TEXT, p_full_name TEXT DEFAULT NULL)
RETURNS TABLE (profile_id UUID, profile_email TEXT, profile_name TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_id UUID;
    v_email TEXT;
    v_name TEXT;
BEGIN
    v_email := lower(trim(p_email));
    SELECT p.id, p.email, p.full_name INTO v_id, v_email, v_name
    FROM public.profiles p
    WHERE lower(p.email) = v_email;

    IF v_id IS NULL THEN
        v_id := gen_random_uuid();
        v_name := COALESCE(nullif(trim(p_full_name), ''), split_part(v_email, '@', 1));
        INSERT INTO public.profiles (id, email, full_name)
        VALUES (v_id, v_email, v_name);
    END IF;

    RETURN QUERY SELECT v_id, v_email, v_name;
END;
$$;

ALTER FUNCTION public.lookup_or_create_profile(TEXT, TEXT) OWNER TO postgres;
REVOKE ALL ON FUNCTION public.lookup_or_create_profile(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lookup_or_create_profile(TEXT, TEXT) TO authenticated;

-- ------------------------------------------------------------------------------
-- 10. Supabase Storage Security Policies (storage.objects)
-- ------------------------------------------------------------------------------

-- Ensure storage bucket exists
INSERT INTO storage.buckets (id, name, public)
VALUES ('workspace-assets', 'workspace-assets', false)
ON CONFLICT (id) DO UPDATE SET public = false;

ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS storage_objects_select_policy ON storage.objects;
CREATE POLICY storage_objects_select_policy ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id = 'workspace-assets'
        AND public.is_workspace_member((split_part(name, '/', 1))::uuid)
    );

DROP POLICY IF EXISTS storage_objects_insert_policy ON storage.objects;
CREATE POLICY storage_objects_insert_policy ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id = 'workspace-assets'
        AND public.is_workspace_member((split_part(name, '/', 1))::uuid)
        AND (
            public.has_workspace_role((split_part(name, '/', 1))::uuid, 'admin')
            OR public.has_workspace_role((split_part(name, '/', 1))::uuid, 'manager')
            OR public.has_workspace_role((split_part(name, '/', 1))::uuid, 'creator')
        )
    );

DROP POLICY IF EXISTS storage_objects_delete_policy ON storage.objects;
CREATE POLICY storage_objects_delete_policy ON storage.objects
    FOR DELETE TO authenticated
    USING (
        bucket_id = 'workspace-assets'
        AND public.is_workspace_member((split_part(name, '/', 1))::uuid)
        AND (
            public.has_workspace_role((split_part(name, '/', 1))::uuid, 'admin')
            OR owner = auth.uid()
        )
    );

-- ------------------------------------------------------------------------------
-- 11. Table-Level Grants & Revocations for Least-Privilege Role
-- ------------------------------------------------------------------------------

-- Revoke blanket privileges
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;

-- Explicit Table Grants for authenticated role
GRANT SELECT, INSERT, UPDATE, DELETE ON public.profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workspaces TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workspace_members TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.source_documents TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.source_passages TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.catalogue_versions TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.rules TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.approved_facts TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.tone_attributes TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.assets TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.content_items TO authenticated;
GRANT SELECT, INSERT ON public.content_versions TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.review_runs TO authenticated;
GRANT SELECT ON public.findings TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.content_comments TO authenticated;
GRANT SELECT, INSERT ON public.content_approvals TO authenticated;
GRANT SELECT ON public.audit_logs TO authenticated;

-- Grant sequence usages
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
