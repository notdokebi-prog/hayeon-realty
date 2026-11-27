-- 하연이 부동산 게시판 테이블
-- Supabase 대시보드 > SQL Editor 에 붙여 넣고 Run 하세요.

create table if not exists public.board_posts (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  author      text not null check (char_length(author) between 1 and 20),
  title       text not null check (char_length(title) between 1 and 80),
  body        text not null check (char_length(body) between 1 and 2000)
);

-- 행 단위 보안: 누구나 읽고 쓸 수 있지만, 고치거나 지우는 건 대시보드(관리자)에서만
alter table public.board_posts enable row level security;

drop policy if exists "누구나 읽기" on public.board_posts;
create policy "누구나 읽기" on public.board_posts
  for select to anon, authenticated using (true);

drop policy if exists "누구나 글쓰기" on public.board_posts;
create policy "누구나 글쓰기" on public.board_posts
  for insert to anon, authenticated with check (true);
